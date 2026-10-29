---
name: google-error-messages
description: >-
  Write actionable user-facing error messages.
---

# Google Helpful Error Messages

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Identify the error's cause

Tell users exactly what went wrong. Be specific—vague error messages
frustrate users.

Not recommended

> Bad directory.

Recommended

> The *[Name of directory]* directory exists but is not writable. To add
> files to this directory, the directory must be writable. *[Explanation of
> how to make this directory writable.]*


## Specify requirements and constraints

Help users understand requirements and constraints. Be specific.
Don't assume that users know the limitations of your system.

Not recommended

> The combined size of the attachments is too big.

Recommended

> The combined size of the attachments (14MB) exceeds the allowed limit (10MB).
> *[Details about possible solution.]*

Not recommended

> Permission denied.

Recommended

> Permission denied. Only users in <group name> have access.
> *[Details about adding users to the group.]*


## Explain how to fix the problem

Create **actionable error messages**. That is, after explaining the cause of
the problem, explain how to fix the problem.

Not recommended

> The client app on your device is no longer supported.

Recommended

> The client app on your device is no longer supported. To update the client app,
> click the **Update app** button.


## Format error messages to enhance readability

### Link to more detailed documentation

When an error requires a lengthy explanation (for example, multiple sentences)
and appropriate documentation is available, use links to redirect users to
more detailed documentation.

### Use progressive disclosure

Some error messages are long, requiring a lot of text to explain the problem
and solution. Unfortunately, users sometimes ignore long error messages,
intimidated by the "wall of text." A good compromise is to display a briefer
version of the error message and then give users the option to click something
to get the full context.

### Place error messages close to the error

For coding errors, place error messages as close as possible to the place
where the error occurred.


## Course summary

This course recommended the following best practices when writing
error messages:

- Identify the cause of the error.
  - If the user entered an invalid value, specify the invalid value.
  - Specify requirements and constraints, such as required permissions
    or minimum RAM.
- Explain how to fix the problem.
  - When appropriate, provide an example to help demonstrate the fix.
- Write clearly.
  - Be concise, not wordy. However, don't be so concise that the resulting
    error message becomes cryptic.
  - Avoid double negatives and exceptions to exceptions.
  - Aim the message at the appropriate target audience. Words appropriate
    for software engineers are often inappropriate for non-technical users.
  - Use terminology consistently. For example, don't use the term *directory*
    in one part of an error message and a *folder* in another part.
  - Format long error messages carefully, possibly using progressive
    disclosure or links to expanded documentation.
  - Set a positive tone.
  - Don't be overly apologetic.
