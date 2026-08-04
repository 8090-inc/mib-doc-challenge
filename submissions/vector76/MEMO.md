# Technical Memo

This is basically the only human-written file in the entire entry.

# Approach (meta)

My (lazy) ideal intended approach and the starting point is to point the AI at the problem, give it space for a solution, and say solve it.  It immediately chose Tesseract and set up a pipeline that could get a score of about 111 almost completely autonomously.

The next step was to set up a pipeline of experiments and enough scaffolding (strategy documents) to let it operate autonomously and in parallel, in worktrees.  I said I wanted to optimize for calendar time and it should parallelize workers for faster test execution and also work parallel worktrees where possible to burn tokens faster.  Overnight, unattended, this got it up to about 120.

What followed was a long slog of mostly failed experiments and misattribution of errors.  I saw failed reads on what looked like eroded pages and also on "strip-sheared" documents and erroneously thought that this was dominating the errors when it wasn't.  They were just the most obvious because of how I was looking at the failures.  If I had studied the errors in a more grounded, data-centric way, I would have seen that I was sinking effort into a minority issue.

Eventually I realized that reversing the image degradation, while interesting, is barely adding any points.  I switched to exploring rules and rule ordering to reflect the underlying adjudication rules.

# Approach (algorithm)

The algorithm is an organic hodge-podge of rules derived incrementally without a sound, coherent unifying principle.  Extraction happens per-page, so conflicting results can be unified by page type.

After basic Tesseract extraction, a strip-shear detector (with decent accuracy) detects the presence of strip-shear artifact, measures the direction of the shear, and attempts to reassemble the strips into the original page.  This works okay but not great, and there are only a few documents where it makes a material difference.  These extractions are added to the base extractions.

The extractions feed into the rule engine which feels disordered, but I think it is just a reflection of the rules themselves, where for example missing fields would ordinarily produce NEEDS_REVIEW, unless some denial values are present, in which case the result is DENIED, unless rescinded denial is also present, in which case it's APPROVED.

White text is in some of the training documents and it is mostly correct for the fields and never correct for adjudication.  I call it "bait".  I use the bait only for filling fields where extraction failed and I have no value at all.  These are guaranteed 100% wrong anyway so there is no harm in using bait, even if it is adversarial.  This fills the fields *after* they have been used for adjudication, so it can have no effect on adjudication, and it is impossible for the result to be worse than ignoring altogether.  Using the bait optimistically based on the behavior on the training set would yield points in the training set but it is known to be untrustworthy and I am considering it adversarial.

There is a certain amount of policy tension between the problem statement and the scoring mechanism.  For a simple example, if fee status is missing (no evidence), one might think it should be NEEDS_REVIEW.  But based on the scoring criteria and the rate at which missing fee status should be APPROVED, better scores assume absent fee status is paid.  For another example, false approvals are called "catastrophic" yet they are only penalized 4 points, so the scoring provides pressure on the adjudication that contravenes the problem statement somewhat.

# Failure Modes

Extraction failures on documents that are readable to my eye are attention-grabbing (to me) as I can see "we could have gotten this."  Even if they are not the biggest source of error, it is theoretically possible to make progress.

The rules are messy and ugly and I don't know if there are real failure modes in the gaps in the rules, or if there is some inductive limit, or if there is a limit, how would I know if I have reached it?

# With Another Week

There is still a nonzero amount of information to be squeezed from the bad raster pages.  Speckles, rotated and strip-sheared, and some pages that are not that blurry, all degrade the extraction but would be readable with more advanced processing.

# Other Notes

I found that allowing the Fable (within Claude Code) to steer its own direction in implementing strip-shear correction was very bad compared to a more closely watched, "micromanaged" approach.  It implemented a bunch of garbage trying to correct the strip shear, and couldn't tell that it was garbage, while hand-holding it through specific steps we got to something that had some nonzero benefit, however tiny.

Partway through the exercise, I found myself with several half-finished experiments and a mess where I couldn't keep straight in my head what was even happening.  I hastily assembled a playbook wherein tasks were required to have ending conditions and a dispatcher kept track of them, while I conversed through a frontend concierge who enforced the task hygiene.  These artifacts are not normally in the repository but I have copied them to "playbook-copy.zip" within the solution repository.
