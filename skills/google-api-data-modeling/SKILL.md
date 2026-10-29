---
name: google-api-data-modeling
description: >-
  Design API fields, enums, units, and defaults.
---

# Google API Data Modeling

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Enumerations

### When to use enums

Enums can be more accessible and readable than strings or booleans in many
cases, but they do add overhead when they change. Therefore, enums **should**
receive new values infrequently. While the definition of "infrequently" may
change based on individual use cases, a good rule of thumb is no more than once
a year. For enums that change frequently, the API **should** use a string and
document the format.

Additionally, enums **should not** be used when there is a competing,
widely-adopted standard representation (such as with [language codes](https://en.wikipedia.org/wiki/IETF_language_tag)
or [media types](https://en.wikipedia.org/wiki/Media_type)).


## Field names

### Guidance

Field names **should** be in correct American English.

Field names **should** clearly and precisely communicate the concept being
presented and avoid overly general names that are ambiguous. That said, field
names **should** avoid including unnecessary words. In particular, avoid
including adjectives that always apply and add little cognitive value. For
example, a `proxy_settings` field might be as helpful as
`shared_proxy_settings` if there is no unshared variant.

### Booleans

Boolean fields **should** omit the prefix "is". For example:

- `disabled` (**not** `is_disabled`)
- `required` (**not** `is_required`)


## Quantities

### Guidance

Quantities with a clear unit of measurement (such as bytes, miles, and so on)
**must** include the unit of measurement as the suffix. When appropriate, units
**should** use generally accepted abbreviations, and abbreviations **should not**
be pluralized (for example, `distance_km` rather than `distance_kilometers`).

```proto
// A representation of a non-stop air route.
message Route {
  // The airport where the route begins.
  string origin = 1;

  // The destination airport.
  string destination = 2;

  // The distance between the origin and destination airports.
  // This value is also used to determine the credited frequent flyer miles.
  int32 distance_miles = 3;
}
```

If the quantity is a number of items (for example, the number of nodes in a
cluster), then the field **should** use the suffix `_count` (**not** the prefix
`num_`):

```proto
// A cluster of individual nodes.
message Cluster {
  // The number of nodes in the cluster.
  int32 node_count = 1;
}
```


## Time and duration

### Timestamps

Fields that represent an absolute point in time (independent of any time zone
or calendar) **should** use the [`google.protobuf.Timestamp`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/timestamp.proto) type,
(which uses UNIX timestamps under the hood and hold nanosecond precision).

These fields **should** have names ending in `_time`, such as `create_time` or
`update_time`. For repeated fields, the names **should** end in `_times`
instead.

### Durations

Fields that represent a span between two points in time (independent of any
time zone or calendar) **should** use the
[`google.protobuf.Duration`](https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/duration.proto) type.

To illustrate the distinction between timestamps and durations, consider a
flight record:

```proto
// A representation of a (very incomplete) flight log.
message FlightRecord {
  // The absolute point in time when the plane took off.
  google.protobuf.Timestamp takeoff_time = 1;

  // The length (duration) of the flight, from takeoff to landing.
  google.protobuf.Duration flight_duration = 2;
}
```


## Repeated fields

### Guidance

Resources **may** use repeated fields where appropriate.

```proto
message Book {
  option (google.api.resource) = {
    type: "library.googleapis.com/Book"
    pattern: "publishers/{publisher}/books/{book}"
  };

  string name = 1 [(google.api.field_behavior) = IDENTIFIER];

  repeated string authors = 2;
}
```


## Ranges

### Inclusive or exclusive ranges

Fields representing ranges **should** use inclusive start values and exclusive
end values (half-closed intervals) in most situations; in interval notation:
`[start_xxx, end_xxx)`.

Exclusive end values are preferable for the following reasons:

- It conforms to user expectations, particularly for continuous values such as
  timestamps, and avoids the need to express imprecise "limit values" (e.g.
  `2012-04-20T23:59:59`).
- It is consistent with most common programming languages, including C++, Java,
  Python, and Go.
- It is easier to reason about abutting ranges: `[0, x), [x, y), [y, z)`, where
  values are chainable from one range to the next.


## Generic fields

### Guidance

While generic fields are generally rare, a service **may** introduce generic
field where necessary. There are several approaches to this depending on how
generic the field needs to be; in general, services **should** attempt to
introduce the "least generic" approach that is able to satisfy the use case.


## Sensitive fields

### Guidance

If the sensitive information is _required_ for the resource as a whole to
exist, the data **should** be accepted as an input-only field
with no corresponding output field. Because the sensitive data must be present
for the resource to exist, users of the API may assume that existence of the
resource implies storage of the sensitive data. For example:

```proto
message SelfManagedKeypair {
  string name = 1 [(google.api.field_behavior) = IDENTIFIER];

  // The public key data in PEM-encoded form.
  bytes public_key = 2;

  // The private key data in PEM-encoded form.
  bytes private_key = 3 [
    (google.api.field_behavior) = INPUT_ONLY];
}
```

If the sensitive information is _optional_ within the containing resource, an
output-only boolean field with a postfix of `_set` **should** be used to
indicate whether or not the sensitive information is present. For example:

```proto
message Integration {
  string name = 1 [(google.api.field_behavior) = IDENTIFIER];
  string uri = 2;

  // A secret to be passed in the `Authorization` header of the webhook.
  string shared_secret = 3 [
    (google.api.field_behavior) = INPUT_ONLY];

  // True if a `shared_secret` has been set for this Integration.
  bool shared_secret_set = 4 [
    (google.api.field_behavior) = OUTPUT_ONLY];
}
```


## Unset field values

### Guidance

Services defined in protocol buffers **should** use the `optional` keyword for
primitives if and only if it is necessary to distinguish setting the field to
its default value (`0`, `false`, or empty string) from not setting it at all:

```proto
// A representation of a book in a library.
message Book {
  option (google.api.resource) = {
    type: "library.googleapis.com/Book"
    pattern: "publishers/{publisher}/books/{book}"
  };

  // The name of the book.
  string name = 1 [(google.api.field_behavior) = IDENTIFIER];

  // The rating for the book, from 0 to 5.
  // 0 is distinct from no rating.
  optional int32 rating = 2;
}
```


## Field behavior documentation

### Immutable

The use of `IMMUTABLE` indicates that a field on a resource cannot be changed
after its creation. This can apply to either fields that are input or outputs,
required or optional.

When a service receives an immutable field in an update request (or similar),
even if included in the update mask, the service **should** ignore the field if
the value matches, but **should** error with `INVALID_ARGUMENT` if a change is
requested.

### Required

The use of `REQUIRED` indicates that the field **must** be present (and set to
a non-empty value) on the request or resource.

A field **should** only be described as required if _either_:

- It is a field on a resource that a user provides somewhere as input. In this
  case, the resource is only valid if a "truthy" value is _stored_.
  - When creating the resource, a value **must** be provided for the
    field on the create request.
  - When updating the resource, the user **may** omit the field
    provided that the field is also absent from the field mask, indicating no
    change to the field (otherwise it **must** be provided).
- It is a field on a request message (a message that is an argument to an RPC,
  with a name usually ending in `Request`). In this case, a value **must** be
  provided as part of the request, and failure to do so **must** cause an error
  (usually `INVALID_ARGUMENT`).


## States

### State transition methods

State transition methods are a special type of custom method that are
responsible for transitioning a state field from one enum value to another. As
part of the transition, other fields may also change, e.g. an `update_time`
field. The method definition should look like the following:

```proto
// Publishes a book.
// The `state` of the book after publishing is `PUBLISHED`.
// `PublishBook` can be called on Books in the state `DRAFT`; Books in a
// different state (including `PUBLISHED`) returns an error.
rpc PublishBook(PublishBookRequest) returns (Book) {
  option (google.api.http) = {
    post: "/v1/{name=publishers/*/books/*}:publish"
    body: "*"
  };
}
```
