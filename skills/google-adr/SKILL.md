---
name: google-adr
description: >-
  Record options and rationale in an ADR.
---

# Google Architecture Decision Records

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Architecture decision records overview

An ADR captures the key options available, the main requirements that drive a
decision, and the design decisions themselves. You often store ADRs in a
[Markdown](https://en.wikipedia.org/wiki/Markdown)
file close to the codebase relevant to that decision. If someone needs to
understand the background of a specific architectural decision, such as why you
use a
regional Google Kubernetes Engine (GKE) cluster,
they can review the ADR and then the associated code.

ADRs can also help you run more reliable applications and services. The ADR
helps you understand your current state and troubleshoot when there's a problem.
ADRs also build a collection of engineering decisions to help future decision
choices and deployments.

### When to use ADRs

As you evaluate the products to use, the ADR helps to explain each of your
decisions. You can revisit the ADR as the team evolves and learns more about the
stack and additional decisions are made or adjusted. If you make adjustments,
include the previous decision and why a change is made. This history keeps a
record of how the architecture has changed as business needs evolve, or where
there are new technical requirements or available solutions.

The following prompts help you to know when to create ADRs:

- When you have a technical challenge or question and there's no existing
  basis for a decision, such as a recommended solution, standard operation
  procedure, blueprint, or codebase.
- When you or your team offers a solution that's not documented somewhere
  accessible to the team.
- When there are two or more engineering options and you want to document your
  thoughts and reasons behind the selection.

When you write an ADR, it helps to have potential readers in mind. The primary
readers are members of the team that work on the technology covered by the ADR.
Broader groups of potential readers of the ADR might include adjacent teams who
want to understand your decisions, such as architecture and security teams.

You should also consider that the application might change owners or include new
team members. An ADR helps new contributors understand the background of the
engineering choices that were made. An ADR also makes it easier to plan future
changes.

### Format of an ADR

A typical ADR includes a set of chapters. Your ADRs should help capture what you
feel is important to the application and your organization. Some ADRs might be
one page long, whereas others require a longer explanation.

The following example ADR outline shows how you might format an ADR to include
the information that's important for your environment:

- Authors and the team
- Context and problem you want to solve
- Functional and non-functional requirements you want to address
- Potential critical user journey (CUJ) the decision impacts
- Overview of the key options
- Your decision and reasons behind the accepted choice

To help keep a record of decisions, you might include a timestamp for each
decision to show when the choice was made.

### How ADRs work

ADRs work best when engineers, developers, or application owners can easily
access information they contain. When they have a question about the why
something is done a certain way, they can look at the ADR to find the answer.

To make the ADR accessible, some teams host it in a central wiki that's also
accessible to business owners, instead of in their source control repository.
When someone has a question about a specific engineering decision, the ADR is
there to provide answers.

An ADR is often written in
[Markdown](https://en.wikipedia.org/wiki/Markdown)
to keep it lightweight and text-based. Markdown files can be included in the
source control repository with your application code.

Store your ADRs close to your application code, ideally in the same version
control system. As you make changes to your ADR, you can review previous
versions from source control as needed.

You could also use another medium like a shared Google Doc or an internal wiki.
These alternate locations might be more accessible to users not part of the
ADR's team. Another option is to create your ADR in a source control repository,
but mirror key decisions into a more accessible wiki.
