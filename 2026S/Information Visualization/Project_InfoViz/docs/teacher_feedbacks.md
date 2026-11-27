- The topic is interesting and well-motivated, and the research questions are specific and well-scoped
- The success score definition (combining ownership, review ratio and the playtime) is a thoughtful and well-justified design decision
- Data cleaning is concrete and specific
- The scatter plot (price vs. success factor, colored by genre, sized by ownership) is a good choice. Just keep in mind that using both color and size simultaneously can create visual clutter -> make sure the two channels are clearly distinguishable
- The heatmap aggregating success score by genre and price tier is reasonable but think carefully about what is encoded as color since success score is a quantitative ordered attribute, a sequential color scale is appropriate. If you want to highlight which segments are above or below average, a diverging scale centered at the mean success score might be more informative
- "Tag network or bubble chart" -> please commit to one. A network and a bubble chart are very different encodings and answer different questions
- No mention of how interactive filters are linked across views
Overall a strong proposal with good analytical thinking. A few encoding decisions still need to be pinned down
