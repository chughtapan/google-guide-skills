---
name: google-api-documentation
description: >-
  Document API contracts and field behavior.
---

# Google API Documentation

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Documentation

### Guidance

In APIs defined in protocol buffers, public comments **must** be included over
every component (service, method, message, field, enum, and enum value) using
the protocol buffers comment format. This is important even in cases where the
comment is terse and uninteresting, as numerous tools read these comments and
use them.

Services, in particular, **should** have descriptive comments that explain what
the service is and what users are able to do with it.

**Note:** Many readers will not be native English speakers. Comments **should**
avoid jargon, slang, complex metaphors, pop culture references, or anything
else that will not easily translate. Additionally, many readers will have
different backgrounds and viewpoints; if writing examples involving people,
comments **should** use people who are non-controversial and no longer alive.

### Style

Comments **should** be in grammatically correct American English. However, the
first sentence of each comment **should** omit the subject and be in the
third-person present tense:

```proto
// Creates a book under the given publisher.
rpc CreateBook(CreateBookRequest) returns (Book) {
  option (google.api.http) = {
    post: "/v1/{parent=publishers/*}/books"
    body: "book"
  };
}
```

### Descriptions

Descriptions of messages and fields **should** be brief but complete. Sometimes
comments are necessarily perfunctory because there is little to be said;
however, before jumping to that conclusion, consider whether some of the
following questions are relevant:

- What is it?
- How do you use it?
- What does it do if it succeeds? What does it do if it fails?
- Is it idempotent?
- What are the units? (Examples: meters, degrees, pixels)
- What are the side effects?
- What are common errors that may break it?
  - What is the expected input format?
  - What range of values does it accept? (Examples: `[0.0, 1.0)`, `[1, 10]`)
    - Is the range inclusive or exclusive?
  - For strings, what is the minimum and maximum length, and what characters
    are allowed?
    - If a value is above the maximum length, do you truncate or send an error?
- Is it always present? (Example: "Container for voting information. Present
  only when voting information is recorded.")
- Does it have a default setting? (Example: "If `page_size` is omitted, the
  default is 50.")

### Formatting

Any formatting in comments **must** be in [CommonMark](https://commonmark.org/). Headings and tables
**must not** be used, as these cause problems for several tools, and are
unsuitable for client library reference documentation.

Comments **should** use `code font` for field or method names and for literals
(such as `true`).

Raw HTML **must not** be used.

"ASCII art" attempts to present a diagram within the protos **must not** be
used. The Markdown within the protos is consumed by a large number of renderers,
and any ASCII art is very unlikely to be well-presented by all of them. If
a diagram is useful in order to understand the API, include a link to a
documentation page containing the diagram as an image.

### Cross-references

A comment can "link" to another component (service, method, message, field,
enum, or enum value) as a Markdown reference link. The reference **must** be one
of the following forms:

- The fully-qualified name of the element e.g. `[Book][google.example.v1.Book]`
- A scope-relative reference qualified e.g. `[Sci-Fi genre][Genre.GENRE_SCI_FI]`
- An implied reference e.g. `[Book][]` which equates to `[Book][Book]`

### Deprecations

To deprecate a component (service, method, message, field, enum, or enum value),
the `deprecated` [option](https://developers.google.com/protocol-buffers/docs/proto#options)
**must** be set to `true`, and the first line of the respective comment
**must** start with `"Deprecated: "` and provide alternative solutions for
developers. If there is no alternative solution, a deprecation reason **must**
be given.

### Internal comments

<!-- TODO: This does not work outside of Google.
           We should probably try to get that fixed. -->

Comments **may** be explicitly marked as internal by wrapping internal content
in `(--` and `--)`.
