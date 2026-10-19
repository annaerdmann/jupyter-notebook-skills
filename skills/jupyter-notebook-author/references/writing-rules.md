# Writing rules

The Markdown cells explain what the code does, why, and what the reader should see. Write precise, scientific, clear text for the stated audience. Short sentences. No filler, no promotion, no LLM-typical patterns.

Sources: EU "How to write clearly"; Google developer documentation style guide; Microsoft style guide; "The Science of Scientific Writing" (American Scientist, 1990); "Politics and the English Language" (1946); Wikipedia "Signs of AI writing".

`scripts/check_notebook.py` flags many of the banned patterns automatically. It cannot judge clarity. Re-read every cell yourself.

## Do

- **One idea per sentence.** Aim for 15–20 words; split sentences over 25 words.
- **Context first, new information last.** Start the sentence with what the reader knows; end with what is new.
- **Active voice, imperative for steps.** "Open the dataset." "Select the region." Address the reader as "you" when you need a subject.
- **Concrete facts instead of adjectives.** Dataset IDs, variable names, units, resolution, period, file size, number of files.
- **Define each term and acronym once**, at first use, then use the same word every time. Do not vary terms for elegance.
- **Conditions before instructions.** "To change the area, edit `bbox` in the parameters cell."
- **Explain the step before the code cell**: the action, why it is needed, what output to expect. Start with the action ("Open the file …"), the reason or the function name. Do not start with "The next cell …"; at most a third of step texts may mention "the next cell".
- **After a figure, say what the reader should notice**, based on what the output really shows. Quote a number or location only if a cell prints it or the figure shows it plainly ("about 17 °C, read from the figure" is fine). Give locations with coordinates. Check absolute statements ("stays below 0 °C") against the extreme values.
- **Describe the files the reader opens**: in the dataset table, give the period, time step and area read from the files themselves. Say when two files differ.
- **Explain request parameters** that change how the data are read, in one or two sentences where the request is built.
- **Justify a choice of statistic** in one sentence when another is plausible (daily maximum vs daily sum), and say what the alternative would show. Do not add the alternative analysis.
- **End the conclusion box** with one or two sentences on what the results suggest, repeating any causation caveat from the analysis.
- **Cite sources** for scientific statements: product user guide, ATBD, paper. Link to them.
- **Sentence-case headings**, unless the style source uses title case.
- **Code font** for code, variables, functions, file names and dataset IDs.
- **Alt text** for every image.
- **Match the audience.** For beginners, explain each new function once. For experts, skip what they know. The storyline says which.

## Do not

### Words and phrases
- delve, crucial, pivotal, vital, tapestry, landscape (unless the land surface), realm, foster, testament, underscore, showcase, leverage, utilize, seamless, robust (unless statistically), cutting-edge, state-of-the-art, game-changing, harness, unlock, empower, navigate (unless navigation), journey, embark, dive into, deep dive, comprehensive, meticulous, intricate, myriad, plethora, notably, essentially, ultimately, moreover, furthermore.
- "It is important to note", "It is worth noting", "Note that" (use a Note box if it matters), "In order to" (use "to"), "simply", "just", "easy", "easily", "of course", "obviously", "basically".
- "Let's" and "we will" as filler openers ("Let's dive in", "In this section we will explore"). State what happens: "This section computes the monthly mean."
- Stacked hedges: "may potentially", "could possibly", "might perhaps". Hedge once, and only when the uncertainty is real.

### Patterns
- Negative parallelism for emphasis: "It's not just X, it's Y", "not only … but also".
- Reflexive triads ("fast, flexible and powerful") when there are not three real items.
- Sentences ending in a participle clause that adds a vague evaluation: "…, highlighting the importance of …", "…, ensuring accuracy".
- More than one em dash per cell. Use a full stop, a comma or brackets.
- Opening recaps ("In this notebook, we have …") and closing recaps ("In conclusion", "Overall", "To sum up") that repeat the text. The take-home section states what the reader learned, in new words, in two to five bullets.
- Bold labels at the start of bullets that the bullet then repeats.
- Emojis, exclamation marks, rhetorical questions.
- Vague attributions ("studies show", "experts agree") without a citation.
- Unverifiable superlatives ("the best", "the most powerful").

## Before and after

| Before | After |
|---|---|
| In this section, we will delve into the fascinating world of sea surface temperature data, which plays a crucial role in understanding our climate. | This section opens the sea surface temperature (SST) data. SST is an essential climate variable. |
| It's important to note that the data is quite large, so we will just select a smaller region in order to speed things up. | The full dataset is 12 GB. To keep the download under 200 MB, select the North Sea only. |
| The plot below beautifully showcases the seasonal cycle, highlighting the significant variability. | The plot shows the seasonal cycle. SST peaks in August at about 17 °C and drops to 6 °C in February. |
| Let's now dive into the next step! | (Delete. Start with the next step.) |

## Self-check before hand-over

1. Read each Markdown cell aloud. Cut every word that adds nothing.
2. Does each code cell have a Markdown cell before it saying what and why, without starting with "The next cell"?
3. Is every number and location in the text printed by a cell or plainly visible in a figure?
4. Are all terms defined once and used consistently?
5. Does the text match the audience in the storyline?
6. Did `scripts/check_notebook.py` report any writing findings? Fix them or explain why they are false positives.
