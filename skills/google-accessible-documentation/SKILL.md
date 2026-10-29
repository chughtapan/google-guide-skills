---
name: google-accessible-documentation
description: >-
  Review documentation for accessibility.
---

# Google Accessible Documentation

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Write helpful alt text

### Briefly summarize the image's purpose

Use a short phrase or one or two sentences. Long descriptions interrupt the
reading flow for screen reader users.

- Don't include extra words like "Image of" or "Photo of."
- Capitalize the first word and include a final period.
- Use other punctuation as necessary.

Screen readers generally pause for periods and some other types of
punctuation. Although a final period is not technically required, it
provides auditory separation between the image description and the body
text that follows the image.

### Avoid duplicating the surrounding text

If the meaning of your document would be the same without the image, add
an empty alt text attribute to the image (`alt=""`). Assistive technologies
ignore the empty attribute.

Use empty alt text in the following situations:

- The image is decorative (not informative), such as an image of a horizontal
  line that is meant to be a visual border at the end of a page.

### Describe complex images in your document

The information in a complex image such as a flowchart, graph, or map can be
difficult to describe in a few short sentences. In this situation, provide
a short description of the image in the alt text and a longer textual
description in the main text of your document or on a separate page that you
link to.

- For graphs, you can provide a data table on the same page or on a separate
  page.
- For flowcharts and diagrams, explain the process or parts of your image in the
  text of your document.

For example, the [Software supply chain threats](https://cloud.google.com/software-supply-chain-security/docs/attack-vectors) page
has a diagram with phases of software development and potential entry points for
vulnerabilities and software attacks.

- The alt text for the diagram is `A diagram that shows entry points for
  software supply chain attacks.`
- The body text introduces the image, explains the use of the image
  legend, and then explains each section of the diagram in context.

### Include demographic information only when necessary

When you describe people, include demographic information only if it is critical
to the main point of the image. Otherwise, use *person* or another term that
provides key context about the person's activity or role in the image, such as
*musician*, *basketball player*, *teacher*, or *doctor*.

For information about using appropriate language to describe people, see
[Inclusive language](https://developers.google.com/style/inclusive-documentation) in the Google developer
documentation style guide.


## Add accessible visuals to writing

### Why visual indicators are insufficient

Visual cues like color, shape, and pattern can be effective tools for
communicating information. However, to ensure that content is accessible to a
wide audience, don't rely exclusively on the visual elements, such as the
following:

- colors
- patterns
- images
- font styling
- directional words (for example, "top-right corner")

Instead, use a mix of these visual elements and accompany them with descriptive
text to convey information. It is also important to provide text descriptions or
alternative text when using images, diagrams, or other diagrams.

### Don't rely on color alone

The following example of comma usage, adapted from the [Google
developer documentation style
guide](https://developers.google.com/style/commas#commas-separating-two-independent-clauses), relies only on color (red and green) to communicate important
information, thus excluding anyone who is color blind or otherwise visually
impaired.

In this example, the red sentences use commas incorrectly, and the green
sentences use commas correctly:

- The libraries make feed creation easier, and
  they ensure that only valid feeds are produced.
- The libraries make feed creation easier and they
  ensure that only valid feeds are produced.
- Type your ID and click OK.
- Type your ID, and click OK.

### Use text, color, and symbols for better accessibility

The following example uses the red "thumbs down" and the green "thumbs up"
symbols in addition to text. This change makes it so the text would be clear
even if you removed all color and other visual indicators.

Recommended: The
libraries make feed creation easier, and they ensure that only valid feeds
are produced.

Not recommended: The
libraries make feed creation easier and they ensure that only valid feeds
are produced.


## Edit for accessibility

### Create helpful headings

Headings help your audience understand what's in your document. Clear,
well-structured document headings simplify navigation for people with
cognitive disabilities and those who use screen readers.

- Tag headings with heading elements.
  - HTML: `<h1>`, `<h2>`, `<h3>` ...
  - Markdown: `#`, `##`, `###` ...
- Use a level-1 heading for the page title or main content heading.
- Don't skip levels of the heading hierarchy. For example, don't jump from an
  `<h1>` to an `<h3>`.

References:

- [Headings and titles](https://developers.google.com/style/headings)
- [Cognitive accessibility design pattern:  Make the site hierarchy easy
  to understand and
  navigate](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o2p02-site-structure/)
- [Making content usable for people with cognitive and learning disabilities](https://www.w3.org/TR/coga-usable/#summary-find)

### Include informative link text

People who use screen readers often use them to scan a page to hear just the
links. Use informative link text to ensure that your audience hears meaningful
information, not just "Learn more, learn more, learn more."

- Avoid:
  - [Learn more](https://developers.google.com/style/tables)
  - [Click here](https://developers.google.com/style/tables)
  - [This document](https://developers.google.com/style/tables)
- Good:
  - Learn how to [format tables](https://developers.google.com/style/tables).
  - Read about [machine learning](https://developers.google.com/machine-learning).

> **Bonus:** Informative link text also improves search engine optimization.

### Use straightforward language and short sentences

Other units in this course talk about making visual images accessible to
everyone. Remember that abstract and unfamiliar *written* representations
can also be particularly challenging for users with cognitive or visual
impairments.

Avoid unfamiliar jargon, US-based slang, pop-cultural references, and
complicated linguistic constructions. Use active voice and short sentences,
and define your technical terms on first use if they are not commonly
understood.

### Test your content for accessibility

Finally, to get a feel for some different ways your users might access and
consume your document, try these testing tips:

- Change the zoom level to help accommodate readers on small screens or
  full-size monitors.
- Use only the keyboard to navigate your document. For example, see
  [Keyboard shortcuts in Chrome](https://support.google.com/chrome/answer/157179).
- Use a screen reader:
  - ChromeVox for ChromeOS
  - VoiceOver for Mac

These methods can help you assess the usability of your document for different
audiences as you edit your own and others' documents for accessibility.

**Next unit:** Conclusion
