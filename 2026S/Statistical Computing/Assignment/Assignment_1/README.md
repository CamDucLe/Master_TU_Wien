# Statistical Computing - Assignment 1

This repository contains the solution files for **Case Study 1** of **AKSTA Statistical Computing VU** at **TU Wien** (Summer Semester 2026).

The main deliverable is an R Markdown report that answers the assignment questions and can be rendered to HTML for submission.

## Repository Structure

- `CS1_question.pdf`: original assignment sheet
- `CS1_template.Rmd`: R Markdown source containing the written answers, code, plots, and benchmarks
- `CS1_template.html`: rendered HTML output of the report
- `README.md`: project overview and reproduction notes

## Assignment Topics

The report covers the following tasks:

1. Ratio of Fibonacci numbers
2. Gamma function
3. Weak law of large numbers
4. Central limit theorem
5. Readable and efficient code
6. Measuring and improving performance

## Requirements

To render the report locally, you need:

- R
- the `rmarkdown` package
- the `knitr` package
- the `microbenchmark` package

Install missing packages in R with:

```r
install.packages(c("rmarkdown", "knitr", "microbenchmark"))
```

## How To Render

From this directory, run:

```r
rmarkdown::render("CS1_template.Rmd")
```

Or from the shell:

```sh
Rscript -e 'rmarkdown::render("CS1_template.Rmd")'
```

This generates `CS1_template.html`.

## Submission Notes

According to the note in the template:

- upload the `.Rmd` file and the generated `.html` file (or alternatively a `.pdf`) to TUWEL
- keep explanations in the report text instead of placing them as code comments
- document AI usage if applicable

## Reproducibility

The report includes simulation, plotting, and benchmarking code. Some chunks set a random seed explicitly, while others depend on fresh random draws, so repeated renders may produce slightly different numerical results and plots.
