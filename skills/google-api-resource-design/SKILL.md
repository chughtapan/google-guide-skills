---
name: google-api-resource-design
description: >-
  Model API resources, hierarchies, and names.
---

# Google API Resource Design

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Resource-oriented design

### Guidance

When designing an API, consider the following (roughly in logical order):

- The resources (nouns) the API will provide
- The relationships and hierarchies between those resources
- The schema of each resource
- The methods (verbs) each resource provides, relying as much as possible on
  the standard verbs.

### Resources

A resource-oriented API **should** generally be modeled as a resource
hierarchy, where each node is either a simple resource or a collection of
resources.

A _collection_ contains resources of _the same type_. For example, a publisher
has the collection of books that it publishes. A resource usually has fields,
and resources may have any number of sub-resources (usually collections).

**Note:** While there is some conceptual alignment between storage systems and
APIs, a service with a resource-oriented API is not necessarily a database, and
has enormous flexibility in how it interprets resources and methods. API
designers **should not** expect that their API will be reflective of their
database schema. In fact, having an API that is identical to the underlying
database schema is actually an anti-pattern, as it tightly couples the surface
to the underlying system.

### Methods

Resource-oriented APIs emphasize resources (data model) over the methods
performed on those resources (functionality). A typical resource-oriented API
exposes a large number of resources with a small number of methods on each
resource. The methods can be either the standard methods (Get, List,
Create, Update, Delete), or custom methods.

If the request to or the response from a standard method (or a custom method in
the same *service*) **is** the resource or **contains** the resource, the
resource schema for that resource across all methods **must** be the same.

A resource **must** support at minimum Get: clients must be
able to validate the state of resources after performing a mutation such
as Create, Update, or Delete.

A resource **must** also support List, except for singleton resources
where more than one resource is not possible.

**Note:** A custom method in resource-oriented design does _not_ entail
defining a new or custom HTTP verb. Custom methods use traditional HTTP verbs
(usually `POST`) and define the custom verb in the URI.

APIs **should** prefer standard methods over custom methods; the purpose of
custom methods is to define functionality that does not cleanly map to any of
the standard methods. Custom methods offer the same design freedom as
traditional RPC APIs, which can be used to implement common programming
patterns, such as database transactions, import and export, or data analysis.

### Strong Consistency

For methods that operate on the management plane, the completion of those
operations (either successful or with an error, long-running operation, or
synchronous) **must** mean that the state of the resource's existence and all
user-settable values have reached a steady-state.

- Following a successful create that is the latest mutation on a resource, a get
  request for a resource **must** return the resource.
- Following a successful update that is the latest mutation on a resource, a get
  request for a resource **must** return the final values from the update
  request.
- Following a successful delete that is the latest mutation on a resource, a get
  request for a resource **must** return `NOT_FOUND` (or the resource with the
  `DELETED` state value in the case of soft delete)


## Resource names

### Guidance

All resource names defined by an API **must** be unique within that API. (See
the section on full resource names below for more
information on referring to resources across APIs.)

Resource names are formatted according to the [URI path schema](https://datatracker.ietf.org/doc/html/rfc3986#appendix-A), but without
the leading slash:

publishers/123/books/les-miserables
users/vhugo1802

### Collection identifiers

The collection identifier segments in a resource name **must** be the plural
form of the noun used for the resource. (For example, a collection of
`Publisher` resources is called `publishers` in the resource name.)

- Collection identifiers **must** be concise American English terms.
- Collection identifiers **must** be in `camelCase`.
- Collection identifiers **must** begin with a lower-cased letter and contain
  only ASCII letters and numbers (`/[a-z][a-zA-Z0-9]*/`).
- Collection identifiers **must** be plural.
  - In situations where there is no plural word ("info"), or where the singular
    and plural terms are the same ("moose"), the non-pluralized (singular) form
    is correct. Collection segments **must not** "coin" words by adding "s" in
    such cases (e.g, avoid "infos").
- Within any given single resource name, collection identifiers **must** be
  unique. (e.g. `people/xyz/people/abc` is invalid)

### Resource ID segments

A resource ID segment identifies the resource within its parent collection. In
the resource name `publishers/123/books/les-miserables`, `123` is the resource
ID for the publisher, and `les-miserables` is the resource ID for the book.

- If resource IDs are user-specified, the API **must** document allowed
  formats. User-specified resource IDs **should** conform to [RFC-1034](https://tools.ietf.org/html/rfc1034);
  which restricts to letters, numbers, and hyphen, with the first character
  a letter, the last a letter or a number, and a 63 character maximum.
  - Additionally, user-specified resource IDs **should** restrict letters to
    lower-case (`^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$`).
  - Characters outside of ASCII **should not** be permitted; however, if
    Unicode characters are necessary, APIs **must** follow guidance in
    AIP-210.
- If resource IDs are not user-settable, the API **should** document the
  basic format, and any upper boundaries (for example, "at most 63
  characters").
- For more information, see the create standard method.


## Resource association

### Guidance

A resource **must** have at most one canonical parent, and `List` requests
**must not** require two distinct "parents" to work.


## Declarative-friendly interfaces

### Resources

Resources that are declarative-friendly **must** use only strongly-consistent
standard methods for managing resource lifecycle, which allows tools to support
these resources generically, as well as conforming to other
declarative-friendly guidance (see further reading).

Declarative-friendly resources **should** designate that they follow the
declarative-friendly style:

```proto
message Book {
  option (google.api.resource) = {
    type: "library.googleapis.com/Book"
    pattern: "publishers/{publisher}/books/{book}"
    style: DECLARATIVE_FRIENDLY
  };

  // Name and other fields...
}
```


## Singleton resources

### Guidance

An API **may** define _singleton resources_. A singleton resource **must**
always exist by virtue of the existence of its parent, with one and exactly one
per parent.

For example:

```proto
message Config {
  option (google.api.resource) = {
    type: "api.googleapis.com/Config"
    pattern: "users/{user}/config"
    singular: "config"
    plural: "configs"
  };

  // additional fields including name
}
```
