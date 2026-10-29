---
name: google-api-list-design
description: >-
  Design API pagination, filtering, and ordering.
---

# Google API List Design

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Standard methods: List

### Ordering

`List` methods **may** allow clients to specify sorting order; if they do, the
request message **should** contain a `string order_by` field.

- Values **should** be a comma separated list of fields. For example:
  `"foo,bar"`.
- The default sorting order is ascending. To specify descending order for a
  field, users append a `" desc"` suffix; for example: `"foo desc, bar"`.
- Redundant space characters in the syntax are insignificant.
  `"foo, bar desc"`, `" foo , bar desc "`, and `"foo,bar desc"` are all
  equivalent.
- Subfields are specified with a `.` character, such as `foo.bar` or
  `address.street`.
- The resulting list order **should** be based on the field type's natural
  comparator e.g. numerics ordered numerically, strings ordered
  lexicographically, etc. However, APIs **may** choose to use a different
  ordering; if so, it **must** be documented in the `order_by` definition.
  - Furthermore, [well-known](https://protobuf.dev/reference/protobuf/google.protobuf) types, like `Timestamp` and `Duration` are
    compared as their representative type; `Timestamp` is compared as time e.g.
    before or after, `Duration` is compared as a quantity e.g. more or less.

<!-- TODO(#220): Add a reference to AIP-161 once it is written. -->


## Partial responses

### Guidance

APIs **may** support partial responses. When partial responses are needed, APIs
**should** use view enumerations as the primary pattern. Alternatively, an API
**may** support partial responses via infrastructure-level field mask parameters.


## Pagination

### Guidance

RPCs returning collections of data **must** provide pagination _at the outset_,
as it is a backwards-incompatible change to add
pagination to an existing method.

- Request messages for collections **should** define an `int32 page_size`
  field, allowing users to specify the maximum number of results to return.
  - The `page_size` field **must not** be required.
  - If the user does not specify `page_size` (or specifies `0`), the API
    chooses an appropriate default, which the API **should** document. The API
    **must not** return an error.
  - If the user specifies `page_size` greater than the maximum permitted by the
    API, the API **should** coerce down to the maximum permitted page size.
  - If the user specifies a negative value for `page_size`, the API **must**
    send an `INVALID_ARGUMENT` error.
  - The API **may** return fewer results than the number requested (including
    zero results), even if not at the end of the collection.
- Request messages for collections **should** define a `string page_token`
  field, allowing users to advance to the next page in the collection.
  - The `page_token` field **must not** be required.
  - If the user changes the `page_size` in a request for subsequent pages, the
    service **must** honor the new page size.
  - The user is expected to keep all other arguments to the RPC the same; if
    any arguments are different, the API **should** send an `INVALID_ARGUMENT`
    error.
- The response **must not** be a streaming response.
- Response messages for collections **should** define a
  `string next_page_token` field, providing the user with a page token that may
  be used to retrieve the next page.
  - The field containing pagination results **should** be the first field in
    the message and have a field number of `1`. It **should** be a repeated
    field containing a list of resources constituting a single page of results.
  - If the end of the collection has been reached, the `next_page_token` field
    **must** be empty. This is the _only_ way to communicate
    "end-of-collection" to users.
  - If the end of the collection has not been reached (or if the API can not
    determine in time), the API **must** provide a `next_page_token`.
- Response messages for collections **may** provide an `int32 total_size`
  field, providing the user with the total number of items in the list.
  - This total **may** be an estimate (but the API **should** explicitly
    document that).

### Opacity

Page tokens provided by APIs **must** be opaque (but URL-safe) strings, and
**must not** be user-parseable. This is because if users are able to
deconstruct these, _they will do so_. This effectively makes the implementation
details of your API's pagination become part of the API surface, and it becomes
impossible to update those details without breaking users.

**Warning:** Base-64 encoding an otherwise-transparent page token is **not** a
sufficient obfuscation mechanism.

For page tokens which do not need to be stored in a database, and which do not
contain sensitive data, an API **may** obfuscate the page token by defining an
internal protocol buffer message with any data needed, and send the serialized
proto, base-64 encoded.

Page tokens **must** be limited to providing an indication of where to continue
the pagination process only. They **must not** provide any form of
authorization to the underlying resources, and authorization **must** be
performed on the request as with any other regardless of the presence of a page
token.

### Backwards compatibility

Adding pagination to an existing RPC is a backwards-incompatible change. This
may seem strange; adding fields to proto messages is generally backwards
compatible. However, this change is _behaviorally_ incompatible.

Consider a user whose collection has 75 resources, and who has already written
and deployed code. If the API later adds pagination fields, and sets the
default to 50, then that user's code breaks; it was getting all resources, and
now is only getting the first 50 (and does not know to advance pagination).
Even if the API set a higher default limit, such as 100, the user's collection
could grow, and _then_ the code would break.

For this reason, it is important to always add pagination to RPCs returning
collections _up front_; they are consistently important, and they can not be
added later without causing problems for existing users.

**Warning:** This also entails that, in addition to presenting the pagination
fields, they **must** be _actually implemented_ with a non-infinite default
value. Implementing an in-memory version (which might fetch everything then
paginate) is reasonable for initially-small collections.


## Reading across collections

### Guidance

APIs **may** support reading resources across multiple collections by allowing
users to specify a `-` (the hyphen or dash character) as a wildcard character
in a standard `List` method:

```
GET /v1/publishers/-/books?filter=...
```

- The URI pattern **must** still be specified with `*` and permit the
  collection to be specified; a URI pattern **must not** hard-code the `-`
  character.
- The method **must** explicitly document that this behavior is supported.
- The resources provided in the response **must** use the canonical name of the
  resource, with the actual parent collection identifiers (instead of `-`).
- Services **may** support reading across collections on `List` requests
  regardless of whether the identifiers of the child resources are guaranteed
  to be unique. However, services **must not** support reading across
  collections on `Get` requests if the child resources might have a collision.
- Cross-parent requests **should not** support `order_by`. If they do, the
  field **must** document that it is best effort. This is because cross-parent
  requests introduce ambiguity around ordering, especially if there is
  difficulty reaching a parent (see AIP-217).


## Filtering

### Guidance

APIs **may** provide filtering to users on `List` methods (or similar methods
to query a collection, such as `Search`). If they choose to do so, they
**should** follow the common specification for filters discussed here. The
syntax is formally defined in the EBNF grammar.

When employing filtering, a request message **should** have exactly one
filtering field, `string filter`. Filtering of related objects is handled
through traversal or functions.

### Validation

If a non-compliant or schematically invalid `filter` string is specified,
the API **should** error with `INVALID_ARGUMENT`. Wherever validation is relaxed
for `filter`, the API **must** document the difference.

Schematic validation refers, but is not limited to, the following:

- Fields referenced in the `filter` **must** exist on the filtered schema
- Field values provided in the `filter` **must** align to the type of the field
  - For example, for a field `int32 age` a `filter` like `"age=hello"` is
    invalid
- Field values for bounded data types e.g. `enum` provided in the `filter`
  **must** be a valid value in the set
- Field values for standardized types e.g. `Timestamp` **must** conform to the
  documented standard (see Comparison Operators for a
  list of such types)


## Unreachable resources

### Pagination

While preparing a page of results to fulfill a page fetch RPC e.g. an
AIP-132 Standard List call, if the service encounters any unreachable
resources or collections they **must** do the following:

- Include the resource name for the unreachable resource in the `unreachable`
  response field.
  - The resource name **must** be the most appropriately scoped for the
    unreachable resource or collection.
    - For example, if a specific zone within a region is unreachable, the
      unreachable resource name would be a zonal Location e.g.
      `projects/example/locations/us-west1-a`, but if an entire region is
      unreachable, the resource name would be a regional Location e.g.
      `projects/example/locations/us-west1`.
  - The resource name **must** be included, regardless of restrictive paging
    parameters e.g. `order_by`, when it is identified as unreachable.
- Populate results that were previously considered unreachable on a following
  page if their availability is restored and the paging parameters allow for
  their inclusion.
  - Determining inclusion eligibility based on paging parameters also includes
    any documented default ordering behavior in the absence of user-specified
    ordering in the request.
  - For example, if region `projects/example/locations/us-west1` was unavailable
    in the first page of an ordered paging call, and including its resources
    would violate the ordering, those out-of-order resources are not included in
    the following page.
  - Similarly, if the same exact request is made, and resources previously
    considered unreachable are available again, they **must** be populated,
    within the constraints of the paging parameters.
- Limit the number of unreachable resource names returned in a given response
  if, even after up-scoping the unreachable resource name, the number of
  unreachable resource names exceeds a documented maximum.
  - This maximum **must** be documented in the `unreachable` field comments
    directly.
  - This is independent of the `page_size` set by the caller.
