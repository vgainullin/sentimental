# Methodology

The scientific intent, so implementation choices make sense.

## Question
Do mathematicians differ in style along Berlin's fox (many ideas, broad) and
hedgehog (one big idea, deep) axis, or along other axes, and how has the mix
changed over time?

## Signals per mathematician
| Signal | Source tables | Captures | Blind spot |
|---|---|---|---|
| **MSC entropy**: normalized Shannon entropy of the field distribution | `papers.msc` | Breadth across fields | Depends on how fields are binned; one program spanning fields looks broad |
| **Dispersion**: mean pairwise cosine distance between paper embeddings | `emb/papers.npy` | Semantic breadth, independent of the taxonomy | Noisy below ~20 papers |
| **Coherence**: mean similarity of consecutive papers by date | `emb/papers.npy` | A sustained program; catches the Grothendieck case | Sensitive to publication order |
| **Stance**: how citing sentences describe the work | `citation_contexts` | Reception (builds on, foundational, critiques) | Mathematical prose is near-neutral; needs a citation-intent classifier, not off-the-shelf sentiment |

## Precision (from simulation)
- Hand-estimated field shares: a score's SD is about 15 points, ranks swing about ±7 places, and about 22% of fox/hedgehog labels flip.
- Counting real papers: the SD falls to about 2–4 points at 100 papers and about 1–2 at 300.
- Entropy is biased **downward** at small n, so use a bias correction (Miller–Madow) or the Bayesian posterior below.
- Cohorts of 2–5 people are noise. Aim for hundreds of mathematicians per 50-year bin.

## Target model (not built yet)
A hierarchical Bayesian model with a Dirichlet process mixture:
- Field counts ~ Multinomial(θ_a), with θ_a ~ Dirichlet(α_z). The fox score is the posterior entropy of θ_a.
- Authors are partially pooled within birth cohorts.
- z_a ~ DP mixture gives style clusters with an inferred number of clusters.
- Each cluster jointly generates field counts, embeddings (von Mises–Fisher), and stance (categorical).
- Cluster proportions drift across cohorts (Gaussian random walk or GP).
- Fit with collapsed Gibbs sampling, or NUTS with truncated stick-breaking and marginalized z (Stan or NumPyro); use variational inference at scale.

This pipeline produces every input that model needs.
