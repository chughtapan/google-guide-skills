---
name: google-api-async-and-batch
description: >-
  Design asynchronous and batch API contracts.
---

# Google Async and Batch APIs

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Long-running operations

### Guidance

Individual API methods that might take a significant amount of time to complete
**should** return a [`google.longrunning.Operation`](https://github.com/googleapis/googleapis/blob/master/google/longrunning/operations.proto) object instead of the
ultimate response message.

- The response type **must** be `google.longrunning.Operation`. The `Operation`
  proto definition **must not** be copied into individual APIs.
  - The response **must not** be a streaming response.
- The method **must** include a `google.longrunning.operation_info` annotation,
  which **must** define both response and metadata types.
  - The response and metadata types **must** be defined in the file where the
    RPC appears, or a file imported by that file.
  - If the response and metadata types are defined in another package, the
    fully-qualified message name **must** be used.
  - The response type **should not** be `google.protobuf.Empty` (except for
    `Delete` methods), unless it is certain that response data will
    _never_ be needed. If response data might be added in the future, define an
    empty message for the RPC response and use that.
  - The metadata type is used to provide information such as progress, partial
    failures, and similar information on each `GetOperation` call. The metadata
    type **should not** be `google.protobuf.Empty`, unless it is certain that
    metadata will _never_ be needed. If metadata might be added in the future,
    define an empty message for the RPC metadata and use that.
- APIs with messages that return `Operation` **must** implement the
  [`Operations`](https://github.com/googleapis/googleapis/blob/master/google/longrunning/operations.proto) service. Individual APIs **must not** define their own
  interfaces for long-running operations to avoid non-uniformity.
- If an RPC supports a validate-only mode, the response to a
  validation request **must** be one of the following:
  - A successful response with an `Operation` which is already complete, with
    the `done` field set to `true`, and a valid (but potentially empty) response
    message in the `response` field, wrapped in a `google.protobuf.Any` message.
    The `name` field **may** be empty, to avoid the service having to maintain
    state for successful validation.
  - An immediate error response (typically "bad request")
  - An `Operation` with the `done` field set to `false`, to indicate
    long-running validation. In this case, the `name` field **must** be set,
    to allow clients to poll the long-running validation operation until it
    has completed. Successful validation **must** eventually be represented by
    an operation with `done=true` and a valid (but potentially empty) wrapped
    response message in the `response` field. Unsuccessful validation **must**
    eventually be represented by an operation with `done=true` and the error
    details provided in the `error` field.

### Parallel operations

A resource **may** accept multiple operations that will work on it in parallel,
but is not obligated to do so:

- Resources that accept multiple parallel operations **may** place them in a
  queue rather than work on the operations simultaneously.
- Resources that do not permit multiple operations in parallel (denying any
  new operation until the one that is in progress finishes) **must** return
  `ABORTED` if a user attempts a parallel operation, and include an error
  message explaining the situation.
- Resources with declarative-friendly APIs **may** allow subsequent
  updates to preempt existing operations. In this case, the latest update
  begins processing and previous operations are marked as `ABORTED` with an
  error message explaining the situation.

### Errors

Errors that prevent a long-running operation from _starting_ **must** return an
error response (AIP-193), similar to any other method.

Operations that fail during their execution phase **must** return an
error response (AIP-193), placed in the `Operation.error` [google.rpc.Status](https://github.com/googleapis/googleapis/blob/master/google/rpc/status.proto)
field.

Non-terminal errors that occur over the course of an operation **may** be placed
in the metadata message and the field(s) **must** be AIP-193 compliant
[google.rpc.Status](https://github.com/googleapis/googleapis/blob/master/google/rpc/status.proto).

### Expiration

APIs **may** allow their operation resources to expire after sufficient time
has elapsed after the operation completed.

**Note:** A good rule of thumb for operation expiry is 30 days.


## Jobs

### Guidance

An API **may** define a `Job` resource to represent a particular task with
distinct setup, configuration, and execution:

```proto
message WriteBookJob {
  option (google.api.resource) = {
    type: "library.googleapis.com/WriteBookJob"
    pattern: "publishers/{publisher}/writeBookJobs/{write_book_job}"
  };

  // Name and other fields...
}
```


## Import and export

### Guidance

APIs **may** support import and export operations, which **may** create
multiple new resources, or they **may** populate data into a single resource.

### Partial failures

While partial failures are normally discouraged, import and export RPCs
**should** include partial failure information in the metadata object. Each
individual error **should** be a `google.rpc.Status` object describing the
error. For more on errors, see AIP-193.


## Batch methods: Get

### Guidance

APIs **may** support Batch Get using the following pattern:

- The RPC's name **must** begin with `BatchGet`. The remainder of the RPC name
  **should** be the plural form of the resource being retrieved.
- The request and response messages **must** match the RPC name, with
  `Request` and `Response` suffixes.
- The HTTP verb **must** be `GET`.
- The HTTP URI **must** end with `:batchGet`.
- The URI path **should** represent the collection for the resource, matching
  the collection used for simple CRUD operations. If the operation spans
  parents, a dash (`-`) **may** be accepted as a wildcard.
- There **must not** be a body key in the `google.api.http` annotation.
- The operation **must** be atomic: it **must** fail for all resources or
  succeed for all resources (no partial success). For situations requiring
  partial failures, `List` ([AIP-132](https://aip.dev/132)) methods **should** be used.
  - If the operation covers multiple locations and at least one location is
    down, the operation **must** fail.


## Batch methods: Create

### Atomic vs. Partial Success

- The batch create method **may** support atomic (all resources created or none
  are) or partial success behavior. To make a choice, consider the following
  factors:
  - **Complexity of Ensuring Atomicity:** Operations that are simple
    passthrough database transactions **should** use an atomic operation,
    while operations that manage complex resources **should** use partial
    success operations.
  - **End-User Experience:** Consider the perspective of the API consumer.
    Would atomic behavior be preferable for the given use case, even if it
    means that a large batch could fail due to issues with a single or a few
    entries?
- Synchronous batch create **must** be atomic.
- Asynchronous batch create **may** support atomic or partial success.
  - If supporting partial success, see
    Operation metadata message requirements.


## Batch methods: Update

### Adopting Partial Success

In order for an existing Batch API to adopt the partial success pattern, the API
must do the following:

- The default behavior must be retained to avoid incompatible behavioral
  changes.
- If the API returns an Operation:
  - The request message **must** have a `bool return_partial_success` field.
  - The Operation `metadata_type` **must** include a
    `map<int32, google.rpc.Status> failed_requests` field.
  - When the `bool return_partial_success` field is set to true in a request,
    the API should allow partial success behavior, otherwise it should continue
    with atomic behavior as default.
- If the API returns a direct response synchronously:
  - Since the existing clients will treat a success response as an atomic
    operation, the existing version of the API **must not** adopt the partial
    success pattern.
  - A new version **must** be created instead that returns an Operation and
    follows the partial success pattern described in this AIP.


## Batch methods: Delete

### Communicating partial failures

The AIP recommends using a `map<int32, google.rpc.Status> failed_requests` field
to communicate partial failures, where the key is the index of the failed
request in the original batch request. The other options considered were:

- A `repeated google.rpc.Status` field. This was rejected because it is not
  clear which entry corresponds to which request.
- A `map<string, google.rpc.Status>` field, where the key is the request id of
  the failed request. This was rejected because:
  - Client will need to maintain a map of request_id -> request in order to use
    the partial success response.
  - Populating a request id for the purpose of communicating errors could
    conflict with [AIP-155](https://aip.dev/155) if the service can not
    guarantee idempotency for an individual request across multiple batch
    requests.
- A `repeated FailedRequest` field, where FailedRequest contains the individual
  create request and the `google.rpc.Status`. This was rejected because echoing
  the request payload back in response is discouraged due to additional
  challenges around user data sensitivity.
