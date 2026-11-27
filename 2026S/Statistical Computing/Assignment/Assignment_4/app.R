# Authors:

# Group 27

# Cam Le      - e12551211
# Abdul Hai   - e12504678
# Zixuan Sun  - e12551596


library(shiny)
library(plotly)
library(ggplot2)
library(dplyr)
library(DT)
library(jsonlite)
library(countrycode)
library(maps)
library(viridis)

# Load data
data_cia <- fromJSON("data_cia2.json")

# User-friendly variable names
var_choices <- c(
  "Education expenditure" = "expenditure",
  "Youth unemployment rate" = "youth_unempl_rate",
  "Net migration rate" = "net_migr_rate",
  "Population growth rate" = "pop_growth_rate",
  "Electricity from fossil fuels" = "electricity_fossil_fuel",
  "Life expectancy" = "life_expectancy"
)

# Map data
world_map <- map_data("world")

world_map$ISO3 <- countrycode(
  world_map$region,
  "country.name",
  "iso3c",
  nomatch = NA
)

map_df <- left_join(
  world_map,
  data_cia,
  by = "ISO3"
)

# ========================= UI =========================

ui <- fluidPage(

  titlePanel("CIA World Factbook 2020"),

  p("Welcome to the CIA World Factbook 2020 explorer. Select a variable to visualize it on the world map, inspect its global and per-continent distribution, or compare two variables in the multivariate scatterplot."),

  tabsetPanel(

    # ================= UNIVARIATE =================

    tabPanel(

      "Univariate analysis",

      sidebarLayout(

        sidebarPanel(

          selectInput(
            "variable",
            "Select a variable:",
            choices = var_choices
          ),

          actionButton(
            "show_data",
            "View raw data"
          ),

          br(), br(),

          DTOutput("raw_data")

        ),

        mainPanel(

          tabsetPanel(

            tabPanel(
              "Map",
              br(),
              em("The map shows values of the selected variable. Countries in grey have missing data."),
              br(), br(),
              plotlyOutput("map", height = "700px")
            ),

            tabPanel(

              "Global analysis",

              fluidRow(

                column(
                  6,
                  plotlyOutput("histogram")
                ),

                column(
                  6,
                  plotlyOutput("boxplot")
                )

              )

            ),

            tabPanel(

              "Analysis per continent",

              fluidRow(

                column(
                  6,
                  plotlyOutput("density_continent")
                ),

                column(
                  6,
                  plotlyOutput("box_continent")
                )

              )

            )

          )

        )

      )

    ),

    # ================= MULTIVARIATE =================

    tabPanel(

      "Multivariate analysis",

      sidebarLayout(

        sidebarPanel(

          selectInput(
            "xvar",
            "Select Variable X:",
            choices = var_choices
          ),

          selectInput(
            "yvar",
            "Select Variable Y:",
            choices = var_choices,
            selected = "life_expectancy"
          ),

          selectInput(
            "sizevar",
            "Scale points by:",
            choices = c(
              "Population" = "population",
              "Area" = "area"
            )
          )

        ),

        mainPanel(

          plotlyOutput("scatter", height = "700px")

        )

      )

    )

  )

)

# ========================= SERVER =========================

server <- function(input, output, session) {

  # Shared reactives

  selected_label <- reactive({
    names(var_choices)[var_choices == input$variable]
  })

  univariate_data <- reactive({
    data_cia %>%
      filter(!is.na(.data[[input$variable]]))
  })

  # Raw Data Table

  table_data <- reactive({
    req(input$show_data > 0)

    df <- data_cia %>%
      select(
        Country = country,
        Continent = continent,
        all_of(input$variable)
      )

    names(df)[3] <- selected_label()
    df
  })

  output$raw_data <- renderDT({

    req(table_data())

    datatable(
      table_data(),
      rownames = FALSE,
      options = list(pageLength = 15)
    )

  })

  # Map

  output$map <- renderPlotly({

    lbl <- selected_label()

    plot_map <- map_df %>%
      mutate(value = .data[[input$variable]])

    p <- ggplot(
      plot_map,
      aes(
        long,
        lat,
        group = group,
        fill = value,
        text = paste0(
          "Country: ", country,
          "<br>", lbl, ": ",
          ifelse(is.na(value), "NO DATA", round(value, 2))
        )
      )
    ) +
      geom_polygon(
        colour = "white",
        linewidth = 0.1
      ) +
      scale_fill_viridis_c(
        name = lbl,
        na.value = "grey90"
      ) +
      labs(title = paste("World map:", lbl)) +
      theme_void()

    ggplotly(p, tooltip = "text")

  })

  # Histogram + Density

  output$histogram <- renderPlotly({

    lbl <- selected_label()

    p <- ggplot(
      univariate_data(),
      aes(x = .data[[input$variable]])
    ) +
      geom_histogram(
        aes(y = after_stat(density)),
        bins = 20,
        fill = "grey80",
        color = "black"
      ) +
      geom_density(
        fill = "steelblue",
        alpha = 0.4
      ) +
      labs(
        title = paste("Distribution of", lbl),
        x = lbl,
        y = "Density"
      ) +
      theme_minimal()

    ggplotly(p)

  })

  # Global Boxplot

  output$boxplot <- renderPlotly({

    lbl <- selected_label()

    p <- ggplot(
      univariate_data(),
      aes(y = .data[[input$variable]])
    ) +
      geom_boxplot(fill = "lightblue") +
      labs(
        title = paste("Boxplot of", lbl),
        y = lbl
      ) +
      theme_minimal()

    ggplotly(p)

  })

  # Density per Continent

  output$density_continent <- renderPlotly({

    lbl <- selected_label()

    p <- ggplot(
      univariate_data(),
      aes(
        x = .data[[input$variable]],
        fill = continent
      )
    ) +
      geom_density(alpha = 0.4) +
      labs(
        title = paste("Density of", lbl, "by continent"),
        x = lbl,
        y = "Density",
        fill = "Continent"
      ) +
      theme_minimal()

    ggplotly(p)

  })

  # Boxplot per Continent

  output$box_continent <- renderPlotly({

    lbl <- selected_label()

    p <- ggplot(
      univariate_data(),
      aes(
        x = continent,
        y = .data[[input$variable]],
        fill = continent
      )
    ) +
      geom_boxplot() +
      labs(
        title = paste("Boxplot of", lbl, "by continent"),
        x = "Continent",
        y = lbl
      ) +
      theme_minimal() +
      theme(
        axis.text.x = element_text(
          angle = 45,
          hjust = 1
        )
      )

    ggplotly(p)

  })

  # Scatterplot

  output$scatter <- renderPlotly({

    x_lbl <- names(var_choices)[var_choices == input$xvar]
    y_lbl <- names(var_choices)[var_choices == input$yvar]
    size_lbl <- if (input$sizevar == "population") "Population" else "Area (km²)"

    plot_data <- data_cia %>%
      filter(
        !is.na(.data[[input$xvar]]),
        !is.na(.data[[input$yvar]]),
        !is.na(.data[[input$sizevar]])
      )

    p <- ggplot(
      plot_data,
      aes(
        x = .data[[input$xvar]],
        y = .data[[input$yvar]]
      )
    ) +

      geom_point(
        aes(
          color = continent,
          size = .data[[input$sizevar]],
          text = paste0(
            "Country: ", country,
            "<br>Continent: ", continent,
            "<br>", x_lbl, ": ", round(.data[[input$xvar]], 2),
            "<br>", y_lbl, ": ", round(.data[[input$yvar]], 2)
          )
        ),
        alpha = 0.7
      ) +

      geom_smooth(
        aes(color = continent),
        method = "loess",
        formula = y ~ x,
        se = FALSE
      ) +

      labs(
        title = paste(y_lbl, "vs", x_lbl),
        x = x_lbl,
        y = y_lbl,
        color = "Continent",
        size = size_lbl
      ) +

      theme_minimal()

    ggplotly(p, tooltip = "text")

  })

}

# Run App

shinyApp(ui, server)
