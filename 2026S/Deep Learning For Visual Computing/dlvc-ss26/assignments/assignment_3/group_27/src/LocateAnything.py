import re
import importlib
import inspect
import torch
from PIL import Image
from transformers import AutoConfig, AutoModel, AutoTokenizer, AutoProcessor
from transformers.dynamic_module_utils import get_class_from_dynamic_module


def _patch_attn_check(model_cls) -> None:
    signature = inspect.signature(model_cls._check_and_adjust_attn_implementation)
    if "allow_all_kernels" in signature.parameters:
        return

    original_check = model_cls._check_and_adjust_attn_implementation

    def _compat_check(self, attn_implementation, *args, allow_all_kernels=None, **kwargs):
        return original_check(self, attn_implementation, *args, **kwargs)

    model_cls._check_and_adjust_attn_implementation = _compat_check


def _patch_qwen2_config(config) -> None:
    text_config = getattr(config, "text_config", None)
    if text_config is None:
        return

    if getattr(text_config, "rope_theta", None) is not None:
        return

    rope_scaling = getattr(text_config, "rope_scaling", None)
    if isinstance(rope_scaling, dict):
        rope_theta = rope_scaling.get("rope_theta")
        if rope_theta is not None:
            text_config.rope_theta = rope_theta


def _patch_tied_weights_metadata(model_cls) -> None:
    for attribute_name in ("all_tied_weights_keys", "_tied_weights_keys"):
        if isinstance(getattr(model_cls, attribute_name, None), list):
            setattr(model_cls, attribute_name, {})


class LocateAnythingWorker:
    """Stateful worker that loads the model once and serves perception queries."""

    def __init__(
        self,
        model_path: str = "nvidia/LocateAnything-3B",
        dtype=torch.bfloat16,
    ):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = dtype

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)

        config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
        _patch_qwen2_config(config)
        auto_map = getattr(config, "auto_map", {}) or {}
        model_reference = auto_map.get("AutoModel") or auto_map.get("AutoModelForCausalLM")

        if model_reference is None:
            raise RuntimeError(
                "LocateAnything model config does not expose a remote AutoModel entry. "
                "Please pin a compatible transformers version or update the model revision."
            )

        model_class = get_class_from_dynamic_module(model_reference, model_path)
        _patch_attn_check(model_class)
        _patch_tied_weights_metadata(model_class)

        model_module = importlib.import_module(model_class.__module__)
        qwen2_pretrained_model = getattr(model_module, "Qwen2PreTrainedModel", None)
        if qwen2_pretrained_model is not None:
            _patch_attn_check(qwen2_pretrained_model)
            _patch_tied_weights_metadata(qwen2_pretrained_model)

        qwen2_for_causal_lm = getattr(model_module, "Qwen2ForCausalLM", None)
        if qwen2_for_causal_lm is not None:
            _patch_tied_weights_metadata(qwen2_for_causal_lm)

        qwen2_module_name = f"{model_class.__module__.rsplit('.', 1)[0]}.modeling_qwen2"
        qwen2_module = importlib.import_module(qwen2_module_name)
        qwen2_pretrained_model = getattr(qwen2_module, "Qwen2PreTrainedModel", None)
        if qwen2_pretrained_model is not None:
            _patch_attn_check(qwen2_pretrained_model)
            _patch_tied_weights_metadata(qwen2_pretrained_model)

        qwen2_for_causal_lm = getattr(qwen2_module, "Qwen2ForCausalLM", None)
        if qwen2_for_causal_lm is not None:
            _patch_tied_weights_metadata(qwen2_for_causal_lm)

        self.model = model_class.from_pretrained(
            model_path,
            config=config,
            torch_dtype=dtype,
        ).to(self.device).eval()

    def predict(
        self,
        image: Image.Image,
        question: str,
        generation_mode: str = "hybrid",   # "fast" (MTP) | "slow" (NTP/AR) | "hybrid"
        max_new_tokens: int = 512,
        temperature: float = 0.27,
        verbose: bool = True,
    ) -> dict:
        messages = [
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": question},
            ]}
        ]

        text = self.processor.py_apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        images, videos = self.processor.process_vision_info(messages)
        inputs = self.processor(
            text=[text], images=images, videos=videos, return_tensors="pt"
        ).to(self.device)

        pixel_values = inputs["pixel_values"].to(self.dtype)
        input_ids = inputs["input_ids"]
        image_grid_hws = inputs.get("image_grid_hws", None)

        response = self.model.generate(
            pixel_values=pixel_values,
            input_ids=input_ids,
            attention_mask=inputs["attention_mask"],
            image_grid_hws=image_grid_hws,
            tokenizer=self.tokenizer,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            generation_mode=generation_mode,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.1,
            verbose=verbose,
        )

        result = {"answer": response[0] if isinstance(response, tuple) else response}
        if isinstance(response, tuple) and len(response) >= 3:
            result["history"] = response[1]
            result["stats"] = response[2]
        return result

    # ---- Convenience methods for each task ----

    def detect(self, image: Image.Image, categories: list[str], **kwargs) -> dict:
        """Object detection / document layout analysis."""
        cats = "</c>".join(categories)
        prompt = (
            f"Locate all the instances that match the following description: {cats}."
            # "Bounding box: <ref>label</ref><box><x1><y1><x2><y2></box>. "
            # "Use integers in [0, 1000] for the coordinates."
        )
        return self.predict(image, prompt, **kwargs)

    # ---- Utility: parse model output ----


    def parse_boxes(self, answer: str, image_width: int, image_height: int) -> list[dict]:
        """Parse model output into labeled pixel-coordinate bounding boxes.

        Coordinates in model output are normalized integers in [0, 1000].
        """
        boxes = []
        pattern = re.compile(
            r"<ref>(.*?)</ref>\s*<box>(?:None|<(\d+)><(\d+)><(\d+)><(\d+)>)</box>",
            re.DOTALL,
        )

        for m in pattern.finditer(answer):
            label, x1, y1, x2, y2 = m.groups()
            if None in (x1, y1, x2, y2):
                continue

            boxes.append({
                "class": label.strip().lower(),
                "x1": int(x1) / 1000 * image_width,
                "y1": int(y1) / 1000 * image_height,
                "x2": int(x2) / 1000 * image_width,
                "y2": int(y2) / 1000 * image_height,
            })

        return boxes
