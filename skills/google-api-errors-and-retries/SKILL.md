---
name: google-api-errors-and-retries
description: >-
  Design API errors, request IDs, and retries.
---

# Google API Errors and Retries

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Errors

### Guidance

Services **must** return a [`google.rpc.Status`](https://github.com/googleapis/googleapis/blob/master/google/rpc/status.proto) message when an
API error occurs, and **must** use the canonical error codes defined in
[`google.rpc.Code`](https://github.com/googleapis/googleapis/blob/master/google/rpc/code.proto).  More information about the particular codes
is available in the [gRPC status code documentation](https://github.com/grpc/grpc/blob/master/doc/statuscodes.md).

Error messages **should** help a reasonably technical user *understand*
and *resolve* the issue, and **should not** assume that the user is an
expert in your particular API. Additionally, error messages **must not**
assume that the user will know anything about its underlying
implementation.

Error messages **should** be brief but actionable. Any extra information
**should** be provided in the `details` field. If even more information
is necessary, you **should** provide a link where a reader can get more
information or ask questions to help resolve the issue. It is also
important to [set the right tone](https://developers.google.com/tech-writing/error-messages/set-tone) when writing messages.

### Status.message

The `message` field is a developer-facing, human-readable "debug message"
which **should** be in English. (Localized messages are expressed using
a `LocalizedMessage` within the `details` field. See
`LocalizedMessage` for more details.) Any dynamic aspects of
the message **must** be included as metadata within the `ErrorInfo` that appears
in `details`.

The message is considered a problem description. It is intended for
developers to understand the problem and is more detailed than
[`ErrorInfo.reason`](https://github.com/googleapis/googleapis/blob/master/google/rpc/error_details.proto#L57), discussed later.

Messages **should** use simple descriptive language that is easy to understand
(without technical jargon) to clearly state the problem that results in an
error, and offer an actionable resolution to it.

### Status.code

The `code` field is the status code, which **must** be the numeric value of
one of the elements of the [`google.rpc.Code`](https://github.com/googleapis/googleapis/blob/master/google/rpc/code.proto) enum.

For example, the value `5` is the numeric value of the `NOT_FOUND`
enum element.

### Status.details

The `details` field allows messages with additional error information to
be included in the error response, each packed in a `google.protobuf.Any`
message.

Google defines a set of [standard detail payloads](https://github.com/googleapis/googleapis/blob/master/google/rpc/error_details.proto) for error
details, which cover most common needs for API errors.
Services **should** use these standard detail payloads when feasible.

Each type of detail payload **must** be included at most once. For
example, there **must not** be more than one [`BadRequest`](https://github.com/googleapis/googleapis/blob/477a59d764428136ba1d857a9633c0d231de6efa/google/rpc/error_details.proto#L168-L218)
message in the `details`, but there **may** be a `BadRequest` and a
[`PreconditionFailure`](https://github.com/googleapis/googleapis/blob/6f3fcc058ff29989f6d3a71557a44b5e81b897bd/google/rpc/error_details.proto#L139-L166).

### ErrorInfo

The [`ErrorInfo`](https://github.com/googleapis/googleapis/blob/6f3fcc058ff29989f6d3a71557a44b5e81b897bd/google/rpc/error_details.proto#L27-L76) message is the primary way to send a
machine-readable identifier. Contextual information **should** be
included in `metadata` in `ErrorInfo` and **must** be included if it
appears within an error message.

The `reason` field is a short snake_case description of the cause of the
error. Error reasons are unique within a particular domain of errors.
The reason **must** be at most 63 characters and match a regular expression of
`[A-Z][A-Z0-9_]+[A-Z0-9]`. (This is UPPER_SNAKE_CASE, without leading
or trailing underscores, and without leading digits.)

The reason **should** be terse, but meaningful enough for a human reader to
understand what the reason refers to.

Good examples:

- `CPU_AVAILABILITY`
- `NO_STOCK`
- `CHECKED_OUT`
- `AVAILABILITY_ERROR`

### Changing error messages

Changing the content of `Status.message` over time must be done carefully,
to avoid breaking clients who have previously had to rely on the message
for all information. See the rationale section
for more details.

For a given RPC:

- If the RPC has *always* returned `ErrorInfo` with machine-readable
  information, the content of `Status.message` **may** change over time.
  (For example, the API producer may provide a clearer explanation,
  or more request-specific information.)
- Otherwise, the content of `Status.message` **must** be stable,
  providing the same text with the same request-specific information.
  Instead of changing `Status.message`, the API **should** include a
  `LocalizedMessage` within `Status.details`.

### Partial errors

APIs **should not** support partial errors. Partial errors add
significant complexity for users, because they usually sidestep the use
of error codes, or move those error codes into the response message,
where the user **must** write specialized error handling logic to
address the problem.

However, occasionally partial errors are necessary, particularly in bulk
operations where it would be hostile to users to fail an entire large
request because of a problem with a single entry.

### Permission Denied

If the user does not have permission to access the resource or parent,
regardless of whether or not it exists, the service **must** error with
`PERMISSION_DENIED` (HTTP 403). Permission **must** be checked prior to
checking if the resource or parent exists.

If the user does have proper permission, but the requested resource or
parent does not exist, the service **must** error with `NOT_FOUND` (HTTP
404).


## Automatic retry configuration

### Guidance

Clients **should** automatically retry requests for which repeated runs would
not cause unintended state changes, which are non-transactional, and which are
[unary](https://grpc.io/docs/guides/concepts/).

Clients **should not** automatically retry transactional requests; instead
these requests **should** have application-level retry logic that retries the
entire transaction block from the start.

### Retryable codes

For methods listed as retryable above, clients **should** retry the following
error codes:

- `UNAVAILABLE`: This code generally results from network hiccups, and is
  generally transient. It is retryable under the expectation that the
  connection will become available (soon).

### Non-retryable codes

The following codes **should not** be automatically retried for any request:

- `OK`: The request succeeded.
- `CANCELLED`: An application can cancel a request, which **must** be honored.
- `DEADLINE_EXCEEDED`: An application can set a deadline, which **must** be
  honored.
- `INVALID_ARGUMENT`: Retrying a request with an invalid argument will never
  succeed.
- `DATA_LOSS`: This is an unrecoverable error and **must** immediately be
  surfaced to the application.


## Request identification

### Guidance

APIs **may** add a `string request_id` parameter to request messages (including
those of standard methods) in order to uniquely identify particular requests.

```proto
message CreateBookRequest {
  // The parent resource where this book will be created.
  // Format: publishers/{publisher}
  string parent = 1 [
    (google.api.field_behavior) = REQUIRED,
    (google.api.resource_reference) = {
      child_type: "library.googleapis.com/Book"
    }];

  // The ID to use for the book, which will become the final component of
  // the book's resource name.
  //
  // This value should be 4-63 characters, and valid characters
  // are /[a-z][0-9]-/.
  string book_id = 2 [(google.api.field_behavior) = REQUIRED];

  // The book to create.
  Book book = 3 [(google.api.field_behavior) = REQUIRED];

  // A unique identifier for this request. Restricted to 36 ASCII characters.
  // A random UUID is recommended.
  // This request is only idempotent if a `request_id` is provided.
  string request_id = 4 [(google.api.field_info).format = UUID4];
}
```

- Providing a request ID **must** guarantee idempotency.
  - If a duplicate request is detected, the server **should** return the
    response for the previously successful request, because the client most
    likely did not receive the previous response.
  - APIs **may** choose any reasonable timeframe for honoring request IDs.
- The `request_id` field **must** be provided on the request message to which
  it applies (and it **must not** be a field on resources themselves).
- Request IDs **should** be optional.
- Request IDs **should** be able to be UUIDs, and **may** allow UUIDs to be the
  only valid format. The format restrictions for request IDs **must** be
  documented.
  - Request IDs that are UUIDs **must** be annotated with the
    `google.api.FieldInfo.Format` value `UUID4` using the extension
    `(google.api.field_info).format = UUID4`. See AIP-202 for more.


## Authorization checks

### Guidance

Services **must** check authorization before validating any request, to ensure
both a secure API surface and a consistent user experience. An operation
**may** require multiple permissions or preconditions in order to grant
authorization.

If a request can not pass the authorization check for any reason, the service
**must** error with `PERMISSION_DENIED`, and the corresponding error message
**should** look like: "Permission '`{p}`' denied on resource '`{r}`' (or it
might not exist)." This avoids leaking resource existence.

If it is not possible to determine authorization for a resource because the
resource does not exist, the service **should** check authorization to read
children on the parent resource, and return `NOT_FOUND` if the authorization
check passes.
