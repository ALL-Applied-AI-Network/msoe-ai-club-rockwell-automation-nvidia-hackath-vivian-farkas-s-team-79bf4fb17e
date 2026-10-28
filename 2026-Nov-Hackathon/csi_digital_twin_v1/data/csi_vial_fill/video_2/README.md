# Video 2 vial-fill data

This folder contains the vial-fill Video 2 source extracted from the supplied
dataset ZIP. The video is 640 × 480 at 30 fps and the dataset documents three
vials. No recipe labels are provided for this video.

The exploratory comparison against Video 5's recipe references is in
`../unlabeled_video_analysis/RECIPE_CANDIDATE_ASSESSMENT.md`. The collar signal
has an additional low-signal run beginning at frame 0, which the analysis treats
as a likely startup artifact before finding the three documented vial
departures. This does not assign confirmed recipe IDs. Regenerate Videos 1-4
together from the project root with
`python tools/analyze_unlabeled_video_recipes.py`.
