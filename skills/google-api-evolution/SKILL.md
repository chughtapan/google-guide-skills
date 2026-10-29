---
name: google-api-evolution
description: >-
  Evaluate API compatibility and versioning.
---

# Google API Evolution

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Backwards compatibility

### Guidance

Existing client code **must not** be broken by a service updating to a new
minor or patch release. Old clients **must** be able to work against newer
servers (with the same major version number).

**Important:** It is not always clear whether a change is compatible or not.
The guidance here **should** be treated as indicative, rather than as a
comprehensive list of every possible change.

There are three distinct types of compatibility to consider:

1. Source compatibility: Code written against a previous version **must**
   compile against a newer version, and successfully run with a newer version
   of the client library.
2. Wire compatibility: Code written against a previous version **must** be able
   to communicate correctly with a newer server. In other words, not only are
   inputs and outputs compatible, but the serialization and deserialization
   expectations continue to match.
3. Semantic compatibility: Code written against a previous version **must**
   continue to receive what most reasonable developers would expect. (This can
   be tricky in practice, however, and sometimes determining what users will
   expect can involve a judgment call.)

### Adding components

In general, new components (interfaces, methods, messages, fields, enums, or
enum values) **may** be added to existing APIs in the same major version.

However, keep the following guidelines in mind when doing this:

- Code written against the previous surface (and thus is unaware of the new
  components) **must** continue to be treated the same way as before.
  - New required fields **must not** be added to existing request messages or
    resources.
  - Any field being populated by clients **must** have a default behavior
    matching the behavior before the field was introduced.
    - This can be tricky to do in some cases. For example, adding pagination
      after the fact where previously all items were returned (i.e. `page_size`
      is infinite, which is not advised). If the default for the new `page_size`
      field is _less_ than what was previously returned, older clients will
      incorrectly assume all results were returned.
  - Any field previously populated by the server **must** continue to be
    populated, even if it introduces redundancy.
- For enum values specifically, be aware that it is possible that user code
  does not handle new values gracefully.
  - Enum values **may** be freely added to enums which are only used in request
    messages.
  - Enums that are used in response messages or resources and which are
    expected to receive new values **should** document this. Enum values still
    **may** be added in this situation; however, appropriate caution **should**
    be used.

### Removing or renaming components

Existing components (interfaces, methods, messages, fields, enums, or enum
values) **must not** be removed from existing APIs in the same major version.
Removing a component is a backwards incompatible change.

**Important:** Renaming a component is semantically equivalent to "remove and
add". In cases where these sorts of changes are desirable, a service **may**
add the new component, but **must not** remove the existing one. In situations
where this can allow users to specify conflicting values for the same semantic
idea, the behavior **must** be clearly specified.

### Changing the type of fields

Existing fields and messages **must not** have their type changed, even if the
new type is wire-compatible, because type changes alter generated code in a
breaking way.

### Semantic changes

Code will often depend on API behavior and semantics, _even when such behavior
is not explicitly supported or documented_. Therefore, APIs **must not** change
visible behavior or semantics in ways that are likely to break reasonable user
code, as such changes will be seen as breaking by those users.

**Note:** This does involve some level of judgment; it is not always clear
whether a proposed change is likely to break users, and an expansive reading of
this guidance could ostensibly prevent _any_ change (which is not the intent).

### Default values must not change

Default values are the values set by servers for resources when they are not
specified by the client. This section only applies to static default values within
fields on resources and does not apply to dynamic defaults such as the default IP
address of a resource.

Changing the default value is considered breaking and **must not** be done. The
default behavior for a resource is determined by its default values, and this
**must not** change across minor versions.


## Stability levels

### Alpha

An _alpha_ component undergoes rapid iteration with a known set of users who
**must** be tolerant of change. The number of users **should** be a
curated, manageable set, such that it is feasible to communicate with all
of them individually.

Breaking changes **must** be both allowed and expected in alpha components, and
users **must** have no expectation of stability.

### Beta

A _beta_ component **must** be considered complete and ready to be declared
stable, subject to public testing. Beta components **should** be exposed to an
unknown and potentially large set of users. In other words, beta components
**should not** be behind an allowlist; instead, they **should** be available to
the public.

Because users of beta components tend to have a lower tolerance of change, beta
components **should** be as stable as possible; however, the beta component
**must** be permitted to change over time. These changes **should** be minimal
but **may** include backwards-incompatible changes to beta components.
Backwards-incompatible changes **must** be made only after a reasonable
deprecation period to provide users with an opportunity to migrate their code.
This deprecation period **must** be defined at the time of being marked beta.

### Stable

A _stable_ component **must** be fully-supported over the lifetime of the major
API version. Because users expect such stability from components marked stable,
there **must** be no breaking changes to these components, subject to the
caveats described below.

### Emergency changes

In certain exceptional cases, such as security concerns or regulatory
requirements, any API component **may** be changed in a breaking manner
regardless of its stability level, and a deprecation is not promised in these
situations.


## API Versioning

### Guidance

All Google API interfaces **must** provide a _major version number_, which is
encoded at the end of the protobuf package, and included as the first part of
the URI path for REST APIs. In the event an API needs to make an incompatible
change, consult [AIP-180](https://aip.dev/180) and [AIP-181](https://aip.dev/181) for necessary steps based on the
stability level of the surface in question.

Note: The use of the term "major version number" above is taken from
[semantic versioning](https://semver.org/). However, unlike in traditional semantic versioning,
Google APIs **must not** expose minor or patch version numbers. For
example, Google APIs use `v1`, not `v1.0`, `v1.1`, or `v1.4.2`. From a user's
perspective, major versions are updated in place with minor/patch equivalent
changes, and users receive new functionality without migration.

A new major version of an API **must not** depend on a previous major version of
the same API. An API surface **must not** depend on other APIs, except for in
the cases outlined in [AIP-213](https://aip.dev/213) and [AIP-215](https://aip.dev/215).

### API evolution

Service producers **must** annotate API elements (RPCs, message fields, enum
values) with internal annotations indicating the API version ranges in which
these elements exist. These annotations define API screens, which represent
version-aware lenses on the API surface.

API screens determine request and response shaping in API proxies, and inform
API documentation and API Discovery Documents. Service producers bundle API
versions for publication, and releases of Discovery Documents, API
documentation, and client libraries are built from these bundles.
