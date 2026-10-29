---
name: google-technical-writing
description: >-
  Explain technical topics to a defined audience.
---

# Google Technical Writing

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Audience

### Define your audience

Serious documentation efforts spend considerable time and energy on
defining their audience. These efforts might involve surveys,
user experience studies, focus groups, and documentation testing.
You probably don't have that much time, so this unit takes a simpler
approach.

Begin by identifying your audience's **role**(s). Sample roles include:

- Software engineers
- Technical, non-engineer roles (such as technical program managers)
- Scientists
- Professionals in scientific fields (for example, physicians)
- Undergraduate engineering students
- Graduate engineering students
- Non-technical positions

We happily appreciate that many people in non-technical roles have great
technical and mathematical skills. However, roles remain an essential
first-order approximation in defining your audience. People within the same role
*generally* share certain base skills and knowledge. For example:

- Most software engineers know popular sorting algorithms,
  [big O notation](https://en.wikipedia.org/wiki/Big_O_notation),
  and at least one programming language. Therefore, you can depend on
  software engineers knowing what O(n) means, but you can't depend on
  non-technical roles knowing O(n).
- A research report targeted at physicians should look very different
  from a newspaper article about the same research aimed at a lay audience.
- A professor's explanation of a new machine learning approach to graduate
  students should differ from the explanation to first-year undergraduate
  students.

### Determine what your audience needs to learn

Write down a list of everything your target audience needs to learn
to accomplish goals. In some cases, the list should hold tasks
that the target audience needs to *perform*. For example:

> After reading the documentation, the audience will know how to do
> the following tasks:

> - Use the Zylmon API to list hotels by price.
> - Use the Zylmon API to list hotels by location.
> - Use the Zylmon API to list hotels by user ratings.

### Curse of knowledge

Experts often suffer from **the curse of knowledge**, which means that
their expert understanding of a topic ruins their explanations to newcomers.
As experts, it is easy to forget that novices don’t know what you
already know. Novices might not understand explanations that make
passing reference to subtle interactions and deep systems that the
expert doesn’t stop to explain.

From the novice's point of view, the curse of knowledge is a "File not found"
linker error due to a module not yet compiled.


## Documents

### State your document's scope

A good document begins by defining its scope. For example:

> This document describes the design of Project Frambus.

A better document additionally defines its non-scope—the topics not
covered that the target audience might reasonably expect your document
to cover. For example:

> This document does not describe the design for the related technology,
> Project Froobus.

### Summarize key points at the start

Engineers and scientists are busy people who won't necessarily read all
76 pages of your document. Imagine that your peers might only read
the first paragraph of your document. Therefore, ensure that the start of your
document answers your readers' essential questions.

Professional writers focus considerable energy on page one to increase the
odds of readers making it to page two. However, the start of any long document
is the hardest page to write. Be prepared to revise page one many times.

### Organize the document to meet your audience's needs

After defining the audience's needs, organize the document to help readers
get the information they need. For example, based on the answers in the
previous section, the outline for the document could look as follows:

1. Overview of the algorithm
   - Compare and contrast with quicksort, including Big O comparisons
     - Link to Wikipedia article on quicksort
   - Optimal datasets for the algorithm
2. Implementing the algorithm
   - Implementation in pseudocode
   - Implementation tips, including common mistakes
3. Deeper analysis of algorithm
   - Edge cases
   - Known unknowns

**Next unit:** Punctuation, an optional unit


## Self-editing

### Think like your audience

Who is your audience? Step back and try to read your draft from their point of
view. Make sure the purpose of your document is clear, and provide definitions
for any terms or concepts that might be unfamiliar to your readers.

It can be helpful to outline a persona for your audience. A persona can consist
of any of the following attributes:

- A role, such as *Systems Engineer* or *QA Tester*.
- An end goal, such as *Restore the database*.
- A set of assumptions about the persona and their knowledge and experience.
  For example, you might assume that your persona is:
  - Familiar with Python.
  - Running a Linux operating system.
  - Comfortable following instructions for the command line.

You can then review your draft with your persona in mind. It can be especially
useful to tell your audience about any assumptions you've made. You can also
provide links to resources where they can learn more if they need to brush up on
a specific topic.

Note that relying too heavily on a persona (or two) can result in a document
that is too narrowly focused to be useful to the majority of your readers.

### Read it out loud

Depending on the context, the style of your writing can alienate, engage, or
even bore your audience. The desired style of a given document depends to an
extent on the audience. For example, the contributor guide for a new open source
project aimed at recruiting volunteers might adopt a more informal and
conversational style, while the developer guide for a commercial enterprise
application might adopt a more formal style.

To check if your writing is conversational, read it out loud. Listen for awkward
phrasing, too-long sentences, or anything else that doesn't feel natural.
Alternatively, consider using a [screen
reader](https://en.wikipedia.org/wiki/Screen_reader) to voice the content for
you.

For more information on adjusting the style of your writing to suit your
audience, see Style and authorial tone.


## Creating sample code

### Correct

Sample code should meet the following criteria:

- Build without errors.
- Perform the task it claims to perform.
- Be as production-ready as possible. For example, the code shouldn't
  contain any security vulnerabilities.
- Follow language-specific conventions.

Sample code is an opportunity to directly influence how your users write code.
Therefore, sample code should set the best way to use your product. If
there is more than one way to code the task, code it in the manner
that your team has decided is best. If your team hasn't considered
the pros and cons of each approach, take time to do so.

### Concise

Sample code should be short, including only essential components. When
a novice C programmer wants to learn how to call the `malloc` function,
give that programmer a brief snippet, not the entire Linux source tree.
Irrelevant code can distract and confuse your audience. That said, never
use bad practices to shorten your code; always prefer correctness over
conciseness.

### Understandable

Follow these recommendations to create clear sample code:

- Pick descriptive class, method, and variable names.
- Avoid confusing your readers with hard-to-decipher programming tricks.
- Avoid deeply nested code.
- Optional: Use bold or colored font to draw the reader's attention
  to a specific section of your sample code. However, use highlighting
  judiciously—too much highlighting means the reader won't focus on
  anything in particular.

### Commented

Consider the following recommendations about comments in sample code:

- Keep comments short, but always prefer clarity over brevity.
- Avoid writing comments about *obvious* code, but remember that what
  is obvious to you (the expert) might not be obvious to newcomers.
- Focus your commenting energy on anything non-intuitive in the code.
- When your readers are very experienced with a technology, don't explain
  *what* the code is doing, explain *why* the code is doing it.

Should you place descriptions of code inside code comments or in
text (paragraphs or lists) outside of the sample code? Note that readers
who copy-and-paste a snippet gather not only the code but also any embedded
comments. So, put any descriptions that belong in the pasted code into the code
comments. By contrast, when you must explain a lengthy or tricky concept,
you should typically place the text before the sample program.

**Note:** If you must sacrifice production readiness in order to make the
code shorter and easier to understand, explain your decisions in the comments.

### Reusable

For your reader to easily reuse your sample code, provide the following:

- All information necessary to run the sample code, including any
  dependencies and setup.
- Code that can be extended or customized in useful ways.

Having easy-to-understand sample code that's concise and compiles is
a great start. If it blows up your reader's app, though, they won't
be happy. Therefore, when writing sample code, consider any potential
side effects caused by your code being integrated into another program.
Nobody wants insecure or grossly inefficient code.
