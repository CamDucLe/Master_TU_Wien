(function ($) {
    function normalizeFunctionUrl(url, functionName) {
        if (!url) {
            return url;
        }

        return url
            .replace(/\/webapp\/api\//, "/api/")
            .replace(
                new RegExp(`/api/${functionName}$`),
                `/2015-03-31/functions/${functionName}/invocations`
            )
            .replace(
                new RegExp(`/webapp/2015-03-31/functions/${functionName}/invocations$`),
                `/2015-03-31/functions/${functionName}/invocations`
            );
    }

    function getBaseUrl() {
        const currentUrl = new URL(document.location.href);
        if (currentUrl.protocol === "file:") {
            return "http://localhost:4566";
        }

        const origin = `${currentUrl.protocol}//${currentUrl.host}`
            .replace("://webapp.s3.", "://")
            .replace("://webapp.s3-website.", "://");

        if (currentUrl.host === "localhost:4566" || currentUrl.host === "127.0.0.1:4566") {
            return origin;
        }

        const pathPrefix = currentUrl.pathname.replace(/\/[^/]*$/, "");
        return `${origin}${pathPrefix}`;
    }

    function getInvokeUrl(functionName) {
        const baseUrl = getBaseUrl();
        return normalizeFunctionUrl(
            `${baseUrl.replace(/\/webapp$/, "")}/2015-03-31/functions/${functionName}/invocations`,
            functionName
        );
    }

    function unwrapLambdaResponse(response) {
        if (typeof response === "string") {
            response = JSON.parse(response);
        }
        if (response && typeof response.body === "string") {
            return JSON.parse(response.body);
        }
        return response;
    }

    function showStatus(message, type) {
        const alertClass = type === "success" ? "alert-success" : "alert-danger";
        $("#uploadStatus")
            .removeClass("d-none alert-success alert-danger")
            .addClass(alertClass)
            .text(message);
    }

    function getStoredUrl(functionName) {
        const storageKey = functionName === "presign" ? "functionUrlPresign" : "functionUrlList";
        let url = localStorage.getItem(storageKey);
        if (url) {
            url = normalizeFunctionUrl(url, functionName);
            localStorage.setItem(storageKey, url);
        }
        return url;
    }

    let functionUrlPresign = getStoredUrl("presign");
    if (functionUrlPresign) {
        $("#functionUrlPresign").val(functionUrlPresign);
    }

    let functionUrlList = getStoredUrl("list");
    if (functionUrlList) {
        $("#functionUrlList").val(functionUrlList);
    }

    const statsTemplate = Handlebars.compile($("#stats-template").html());

    $("#configForm").submit(function (event) {
        if (event.preventDefault) {
            event.preventDefault();
        } else {
            event.returnValue = false;
        }

        let action = $(this).find("button[type=submit]:focus").attr("name");
        if (action === undefined && event.originalEvent.submitter) {
            action = event.originalEvent.submitter.getAttribute("name");
        }

        if (action === "load") {
            const presignUrl = getInvokeUrl("presign");
            const listUrl = getInvokeUrl("list");
            $("#functionUrlPresign").val(presignUrl);
            $("#functionUrlList").val(listUrl);
            localStorage.setItem("functionUrlPresign", presignUrl);
            localStorage.setItem("functionUrlList", listUrl);
        } else if (action === "save") {
            localStorage.setItem("functionUrlPresign", $("#functionUrlPresign").val());
            localStorage.setItem("functionUrlList", $("#functionUrlList").val());
        } else if (action === "clear") {
            localStorage.removeItem("functionUrlPresign");
            localStorage.removeItem("functionUrlList");
            $("#functionUrlPresign").val("");
            $("#functionUrlList").val("");
        } else {
            alert("Unknown action");
        }
    });

    $("#uploadForm").submit(function (event) {
        $("#uploadForm button").addClass("disabled");
        $("#uploadStatus").addClass("d-none");

        if (event.preventDefault) {
            event.preventDefault();
        } else {
            event.returnValue = false;
        }

        const functionUrlPresign = $("#functionUrlPresign").val();
        if (!functionUrlPresign) {
            alert("Please set the function URL of the presign Lambda");
            $("#uploadForm button").removeClass("disabled");
            return;
        }

        const reviewerID = $("#reviewerID").val().trim();
        const reviewPayload = {
            reviewerID: reviewerID,
            overall: Number($("#overall").val()),
            summary: $("#summary").val(),
            reviewText: $("#reviewText").val()
        };
        const key = `${reviewerID || "review"}_${Date.now()}.json`;

        $.ajax({
            type: "POST",
            url: functionUrlPresign,
            data: JSON.stringify({key: key}),
            contentType: "application/json",
            success: function (response) {
                const presignedPost = unwrapLambdaResponse(response);
                const formData = new FormData();

                Object.entries(presignedPost.fields).forEach(([field, value]) => {
                    formData.append(field, value);
                });

                formData.append(
                    "file",
                    new Blob([JSON.stringify(reviewPayload)], {type: "application/json"}),
                    key
                );

                $.ajax({
                    type: "POST",
                    url: presignedPost.url,
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function () {
                        showStatus("Review uploaded. The pipeline was triggered asynchronously.", "success");
                        $("#uploadForm")[0].reset();
                        setTimeout(updateStats, 3000);
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        console.error("Upload POST failed", jqXHR.status, textStatus, errorThrown, jqXHR.responseText);
                        showStatus("Upload failed. Check the browser and MiniStack logs.", "error");
                    },
                    complete: function () {
                        $("#uploadForm button").removeClass("disabled");
                    }
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.error("Presign request failed", jqXHR.status, textStatus, errorThrown, jqXHR.responseText);
                showStatus("Could not get a pre-signed URL. Check the Lambda URL and logs.", "error");
                $("#uploadForm button").removeClass("disabled");
            }
        });
    });

    function updateStats() {
        const listUrl = $("#functionUrlList").val();
        if (!listUrl) {
            alert("Please set the function URL of the list Lambda");
            return;
        }

        $.ajax({
            type: "POST",
            url: listUrl,
            data: JSON.stringify({}),
            contentType: "application/json",
            success: function (response) {
                const stats = unwrapLambdaResponse(response);
                $("#statsContainer").html(statsTemplate({
                    total_reviews: stats.total_reviews || 0,
                    positive: stats.positive || 0,
                    neutral: stats.neutral || 0,
                    negative: stats.negative || 0,
                    profane_count: stats.profane_count || 0,
                    banned_users: stats.banned_users || []
                }));
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.error("List request failed", jqXHR.status, textStatus, errorThrown, jqXHR.responseText);
                alert("error! check the logs");
            }
        });
    }

    $("#updateStatsButton").click(function () {
        updateStats();
    });

    if (functionUrlList) {
        updateStats();
    }
})(jQuery);
