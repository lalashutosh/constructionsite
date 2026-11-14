# count_defaults must surface as Tag.defaulted
Raster rules write facts.extras["count_defaults"][intent]={value,reason} when they fall back to the dev-median prior (showers_baths, kitchens, bathrooms).
Integrator (prompts/20) must read that key and emit Tag.defaulted + an assumption, never Tag.drawn. Reviewer checks this in P4.
