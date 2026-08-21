# Page 1 - Executive Overview

High-level operational context. This is a summary page explaining the project.

***DOES THE BEARSPAW BREAK SHOW UP IN MY WATERMAIN-BREAK RECORDS? I WANT TO HIGHLIGHT THAT BREAK***

Include summary of tech-stacks used, link to GitHub repo, maybe single-line "how this was built"

## Data & Methodology

This is an important page. Sources, update frequency, watermain-break lag explanation,  
how community stats are normalized, etc. Maybe should be separate page?

# Page 2 - Infrastructure & Incident Map

"Where are the watermain breaks occurring?"

This lets users visually inspect watermain-breaks.

I want to highlight the limitations of my data here -  
when the city's watermain-break data was last updated,  
and the latest recorded watermain-break in those records.  

The user will be able to filter the date-range they are inspecting.  
The default date-range will be 2024 to current date - as the Bearspaw watermain-break was in 2024.

***I should do something to specifically flag the Bearspaw watermain-break.***

The city will be divided into communities.

Ideally, I'd like to get summary stats per community when you look at them -  
how many watermain breaks did this community get, compared to the average number of breaks per community?  
What percentage of total watermain-breaks did this community account for (during this time period)?

Because larger communities will generally have more breaks, have a way of normalizing watermain-breaks.  
Examples: "Breaks per 1000 people, breaks per 1000 households, breaks per X km of watermains"

# Page 3 - Precipitation (Rainfall) and Watermain-breaks

The user will be able to filter the date-range they are inspecting.  
The default year for this page will be 2013, the year of the "Hell-or-High-Water" stampede year.

Simple concept: over this (time-period) there was X amount of rain per day, there were Y watermain breaks,  
and here are the water-main breaks on the map.

# Page 4 - Temperature and Watermain-breaks

Identifying if temperature-shifts (Chinooks, freezing/thawing events) are correlated with watermain-breaks.

# Page 5 - Watermain-breaks Over Time

Shows a chart of watermain-breaks over time.  
Users can change the time period, and have it show watermain-breaks per community instead of city overall.

Since there's overlap between this page and page 2, ensure we clearly state distinction.

Page 2: spatial snapshot of selected time-period

Page 5: temporal trend, optional community breakdown.