---
name: google-slos
description: >-
  Define SLIs, SLOs, and error budgets.
---

# Google Service-Level Objectives

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Concepts in service monitoring

### Terminology

Service monitoring has a set of core concepts, which are introduced here:

- Service-level indicator (SLI): a measurement of performance.
- Service-level objective (SLO): a statement of desired performance.
- Error budget: starts at 1 - SLO and declines as the actual performance
  misses the SLO.

### Service-level indicators

- Request count: for example, the number of HTTP requests per minute
  that result in 2xx or 5xx responses.
- Response latencies: for example, the latency for HTTP 2xx responses.

- An *availability* SLI is the ratio of the number
  of successful responses to the number of all responses.
- A *latency* SLI is the ratio of the number of calls below
  a latency threshold to the number of all calls.

You can also set up service-specific SLIs for some other measure of
what “good performance” means. These SLIs generally fall into
two categories:

- Request-based SLIs, where good service is measured by counting atomic
  units of service, like the number of successful HTTP requests.
- Windows-based SLIs, where good service is measured by counting the number
  of time periods, or windows, during which performance meets a goodness
  criterion, like response latency below a given threshold.

### Service-level objectives

An SLO is built on the following kinds of information:

- An SLI, which measures the performance of the service.
- A performance goal, which specifies the desired level of performance.
- A time period, called the compliance period, for measuring how the SLI
  compares to the performance goal.

For example, you might have requirements like these:

- Latency can exceed 300 ms in only 5 percent of the requests over a rolling
  30-day period.
- The system must have 99% availability measured over a calendar week.

Changes in SLO compliance can also indicate the onset of failures. Monitoring
these changes might give you enough warning that you can fix a problem before
it cascades. So alerting policies are typically used to monitor SLO compliance.
For more information, see Alerting on your error budget.

### Error budgets

An SLO specifies the degree to which a service must perform during a
compliance period. What's left over in the compliance period becomes the
*error budget*. The error budget quantifies the degree to which a service
can fail to perform during the compliance period and still meet the SLO.

Error budgets let you track how many bad individual events (like requests) are
allowed to occur during the remainder of your compliance period before you
violate the SLO. You can use the error budget to help you manage maintenance
tasks like deployment of new versions. If the error budget is close to depleted,
then taking risky actions like pushing new updates might result in your
violating an SLO.

Your error budget for a compliance period is (1 − *SLO goal*) ×
(*eligible events in compliance period*). For example, if your SLO is for 85%
of requests to be good in a 7-day rolling period, then your error budget allows
15% of these requests to be bad. If you received, say, 60,480 requests in the
past week, your error budget is 15% of that total, or 9,072 requests that are
permitted to be bad. If you served more errors than this, your service was out
of SLO for the 7-day compliance period.

### Designing and using SLOs

SLOs define the target performance you want from your service.
In general, SLOs should be *no higher than necessary or meaningful*.
If your users cannot tell the difference between 99% availability and
99.9% availability of your service, use the lower value as the SLO. The higher
value is more expensive to meet, and it won't make a difference to
your users. A service required to meet a 100% SLO goal has no error budget.
Setting such an SLO is bad practice.

SLOs are typically more stringent than public or contractual
commitments. You want an SLO to be tighter than a public commitment. This way,
if something happens that causes violation of the SLO, you are aware of and
fixing the problem before it causes a violation of a commitment or contract.
Violating a commitment or contract may have reputational, financial, or legal
implications. An SLO is part of an early-warning system to prevent that from
happening.

### Calendar-based compliance periods

Compliance periods can be set to calendar periods like a week or a month.
The compliance period and error budget reset on well-known calendar boundaries.
For the possible values, see `CalendarPeriod`.

With a calendar period, you get a performance score at the end of the period.
Measured against the performance threshold, the performance score lets you
know whether your service was compliant or not. When you use a calendar
period, you only get a compliance rating once every compliance period, even
though you see the performance throughout the period. But the end-of-period
score gives you an easy-to-read value that matches easily against your
customer billing periods (if you have external paying customers).

### Rolling window-based compliance periods

You can also measure compliance over a rolling period, so that you are
always evaluating, for example, the last 30 days. With a rolling period,
the oldest data in the previous calculation drops out of the current
calculation and new data replaces it.

With a rolling window, you get more compliance measurements; that is,
you get a measure of compliance for the last 30 days, rather than one per
month. Services can transition between compliance and noncompliance
as the SLO status changes daily, as old data points are dropped and new ones
added.

### Request-based SLOs

A *request-based SLO* is based on an SLI that is defined as the
ratio of the number of good requests to the total number of requests.
A request-based SLO is met when that ratio meets or exceeds the goal for
the compliance period.

For example, consider this request-based SLO: “Latency is below 100 ms
for at least 95% of requests.” A good request is one with a response
time less than 100 ms, so the measure of compliance is the fraction
of requests with response times under 100 ms. The service is compliant if
this fraction is at least 0.95.

Request-based SLOs give you a sense of what percentage of work your service
did properly over the entire compliance period, no matter how the load was
distributed throughout the compliance period.

### Windows-based SLOs

A *windows-based SLO* is based on an SLI defined as the ratio of the
number of measurement intervals that meets some goodness criterion to the total
number of intervals. A windows-based SLO is met when that ratio meets or exceeds
the goal for the compliance period.

For example, consider this SLO: “The 95th percentile latency metric is
less than 100 ms for at least 99% of 10-minute windows”. A good
measurement period is a 10-minute span in which 95% of the requests
have latency under 100 ms. The measure of compliance is the fraction of
such good periods. The service is compliant if this fraction is at least 0.99.

For another example, suppose you configure your compliance period to be a
rolling 30 days, the measurement interval to be a minute, and the SLO goal to
be 99%. To meet this SLO, your service must have 42,768 “good”
intervals out of 43,200 minutes (99% of the number of minutes in 30 days).

A windows-based SLO gives you an idea of what percentage of the time your
customers found the service to be working well or poorly. This
type of SLO can hide the effects of “bursty” behavior: A
measurement interval that failed every one of its calls counts against the
SLO as much as a measurement interval that had one error too many. Also,
intervals with a low number of calls count against the SLO as much as a
measurement interval with heavy activity.
