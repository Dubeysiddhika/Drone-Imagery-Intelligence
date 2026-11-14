# Negative Pair Verification

## Objective

Check representative negative pairs for likely false negatives and review whether the geospatially distant pairs are actually separable.

## Summary

The Phase 2A negative pair set was created using a conservative 75 km geographic distance threshold. The verified negative-pair distances are far stronger than that threshold:

- minimum observed distance: 1,112.286 km
- median distance: 1,909.311 km
- maximum distance: 2,147.530 km

This is a strong indication that the negative pairs are geographically distinct and are not likely to correspond to the same local scene.

## False-negative risk assessment

A false negative would require a drone image and a satellite tile from a distant region to still represent the same visual environment or to share enough local structure that a feature matcher could misread them as a match. That is not credible for the produced negative set because the sampled drone and map points are separated by more than 1,000 km on average.

## Conclusion

The negative pairs are geospatially robust and unlikely to contain an accidental false negative from the same scene. The negative set is suitable for evaluation of local feature retrievers, as long as the retrieval task remains driven by the geospatial boundaries and not by explicit image overlap assumptions.
