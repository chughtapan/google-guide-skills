---
name: google-api-methods
description: >-
  Design API methods, updates, etags, and masks.
---

# Google API Methods

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Methods

### Choosing a method category

While designing a method, API authors should choose from the defined categories
in the following order:

1. Standard methods (on collections and resources)
1. Standard batch or aggregate methods
1. Custom methods (on collections, resources, or stateless)
1. Streaming methods


## Standard methods: Get

### Guidance

APIs **must** provide a get method for resources. The purpose of the get method
is to return data from a single resource.

```proto
rpc GetBook(GetBookRequest) returns (Book) {
  option (google.api.http) = {
    get: "/v1/{name=publishers/*/books/*}"
  };
  option (google.api.method_signature) = "name";
}
```


## Standard methods: Create

### Guidance

APIs **should** generally provide a create method for resources unless it is
not valuable for users to do so. The purpose of the create method is to create
a new resource in an already-existing collection.

```proto
rpc CreateBook(CreateBookRequest) returns (Book) {
  option (google.api.http) = {
    post: "/v1/{parent=publishers/*}/books"
    body: "book"
  };
  option (google.api.method_signature) = "parent,book";
}
```

### User-specified IDs

An API **must** allow a user to specify the ID component of a resource (the last
segment of the resource name) on creation if the API is operating on the
management plane.

On the data plane, an API **should** allow a user to specify the ID.
Exceptional cases should have the following behavior:

- The data plane resource allows identical records without a need to
  disambiguate between the two (e.g. rows in a table with no primary key).
- The data plane resource will not be exposed in Declarative clients.


## Standard methods: Update

### PATCH and PUT

**TL;DR:** Google APIs generally use the `PATCH` HTTP verb only, and do not
support `PUT` requests.

We standardize on `PATCH` because Google updates stable APIs in place with
backwards-compatible improvements. It is often necessary to add a new field to
an existing resource, but this becomes a breaking change when using `PUT`.

To illustrate this, consider a `PUT` request to a `Book` resource:

PUT /v1/publishers/123/books/456

### Side effects

In general, update methods are intended to update the data within the resource.
Update methods **should not** trigger other side effects. Instead, side effects
**should** be triggered by custom methods.

In particular, this entails that state fields **must not** be directly
writable in update methods.


## Standard methods: Delete

### Guidance

APIs **should** generally provide a delete method for resources unless it is
not valuable for users to do so.

```proto
rpc DeleteBook(DeleteBookRequest) returns (google.protobuf.Empty) {
  option (google.api.http) = {
    delete: "/v1/{name=publishers/*/books/*}"
  };
  option (google.api.method_signature) = "name";
}
```

### Cascading delete

Sometimes, it may be necessary for users to be able to delete a resource as
well as all applicable child resources. However, since deletion is usually
permanent, it is also important that users not do so accidentally, as
reconstructing wiped-out child resources may be quite difficult.

If an API allows deletion of a resource that may have child resources, the API
**should** provide a `bool force` field on the request, which the user sets to
explicitly opt in to a cascading delete.


## Custom methods

### Guidance

Custom methods **should** only be used for functionality that can not be easily
expressed via standard methods; prefer standard methods if possible, due to
their consistent semantics. (Of course, this only applies if the functionality
in question actually conforms to the normal semantics; it is _not_ a good idea
to contort things to endeavor to make the standard methods "sort of work".)

While custom methods vary widely in how they are designed, many principles
apply consistently:

```proto
// Archives the given book.
rpc ArchiveBook(ArchiveBookRequest) returns (ArchiveBookResponse) {
  option (google.api.http) = {
    post: "/v1/{name=publishers/*/books/*}:archive"
    body: "*"
  };
}
```


## Resource freshness validation

### Guidance

A resource **may** include an `etag` field on any resource where it is
important to ensure that the client has an up to date resource before acting on
certain requests:

```proto
// A representation of a book.
message Book {
  // Other fields...

  // This checksum is computed by the server based on the value of other
  // fields, and may be sent on update and delete requests to ensure the
  // client has an up-to-date value before proceeding.
  string etag = 99;
}
```

- The etag field **must** be a string, and **must** be named `etag`.
- The etag field on the _resource_ **should not** be given any behavior
  annotations.
- The etag field **must** be provided by the server on output, and values
  **should** conform to [RFC 7232](https://tools.ietf.org/html/rfc7232#section-2.3).
- If a user sends back an etag which matches the current etag value, the
  service **must** permit the request (unless there is some other reason for
  failure).
- If a user sends back an etag which does not match the current etag value, the
  service **must** send an `ABORTED` error response (unless another error takes
  precedence, such as `PERMISSION_DENIED` if the user is not authorized).
- If the user does not send an etag value at all, the service **should** permit
  the request. However, services with strong consistency or parallelism
  requirements **may** require users to send etags all the time and reject the
  request with an `INVALID_ARGUMENT` error in this case.


## Field masks

### Read-write consistency

Read and write behavior for field masks **must** be self-consistent if a mask
is present:

- If a user updates a resource with a given mask, and then reads the same
  resource with the same mask, the exact same data **must** be returned.
  - Exception: Output only fields.
- Similarly, reading a resource with a given mask and then updating the
  resource with the returned data and the same mask **must** be a no-op.

**Note:** This implies that any mask that is valid for either read or write
**must** be valid for both.


## Change validation

### Guidance

APIs **may** provide an option to validate, but not actually execute, a
request, and provide the same response (status code, headers, and response
body) that it would have provided if the request was actually executed.

To provide this option, the method **should** include a `bool validate_only`
field in the request message:

```proto
message ReviewBookRequest {
  string name = 1 [(google.api.resource_reference) = {
    type: "library.googleapis.com/Book"
  }];
  int32 rating = 2;
  string comment = 3;

  // If set, validate the request and preview the review, but do not actually
  // post it.
  bool validate_only = 4;
}
```
