---
name: google-observability
description: >-
  Design monitoring, instrumentation, and alerts.
---

# Google Monitoring and Observability

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Monitoring and observability

Good monitoring is a staple of high-performing teams.
DORA research
shows that a comprehensive monitoring and observability solution, along with a
number of other technical practices, positively contributes to
continuous delivery.

DORA's research defined these terms as follows:

**Monitoring** is tooling or a technical solution that allows teams to watch
and understand the state of their systems. Monitoring is based on gathering
predefined sets of metrics or logs.

**Observability** is tooling or a technical solution that allows teams to
actively debug their system. Observability is based on exploring properties and
patterns not defined in advance.

### How to implement monitoring and observability

Monitoring and observability solutions are designed to do the following:

-   Provide leading indicators of an outage or service degradation.
-   Detect outages, service degradations, bugs, and unauthorized activity.
-   Help debug outages, service degradations, bugs, and unauthorized activity.
-   Identify long-term trends for capacity planning and business purposes.
-   Expose unexpected side effects of changes or added functionality.

As with all capabilities, installing a tool is not enough to achieve the
objectives, but tools can help or hinder the effort.  Monitoring systems should
not be confined to a single individual or team within an organization.
Empowering all developers to be proficient with monitoring helps develop a
culture of data-driven decision making and improves overall system
debuggability, reducing outages.

There are a few keys to effective implementation of monitoring and
observability. First, your monitoring should tell you what is broken and help
you understand why, before too much damage is done. The key metric in the event
of an outage or service degradation is time-to-restore (TTR). A key contributor
to TTR is the ability to rapidly understand what broke and the quickest path to
restoring service (which may not involve immediately remediating the underlying
problems).

There are two high-level ways of looking at a system: *blackbox* monitoring,
where the system's internal state and mechanisms are not made known, and
*whitebox* monitoring, where they are.

For more information, see "Monitoring Distributed Systems" in the
[Site Reliability Engineering](https://landing.google.com/sre/sre-book/chapters/monitoring-distributed-systems/)
book.

### Blackbox monitoring

In a blackbox (or *synthetic*) monitoring system, input is sent to the system
under examination in the same way a customer might. This might take the form of
HTTP calls to a public API, or RPC calls to an exposed endpoint, or it might be
calling for an entire web page to be rendered as a part of the monitoring
process.

Blackbox monitoring is a sampling-based method. The same system that is
responsible for user requests is monitored by the blackbox system. A blackbox
system can also provide coverage of the target system's surface area.  This
could mean probing each external API method. You might also consider a
representative mixture of requests to better mimic actual customer behavior.
For example, you might perform 100 reads and only 1 write of a given API.

You can govern this process with a *scheduling system*, to ensure that these
inputs are made at a sufficient rate in order to gain confidence in their
sampling. Your system should also contain a *validation engine*, which can be
as simple as checking response codes, or matching output with regular
expressions, up to rendering a dynamic site in a headless browser and traversing
its DOM tree, looking for specific elements. After a decision is made (pass,
fail) on a given probe, you must store the result and metadata for reporting and
alerting purposes.  Examining a snapshot of a failure and its context can be
invaluable for diagnosing an issue.

### Whitebox monitoring

Monitoring and observability rely on signals sent from the workload under
scrutiny into the monitoring system. This can generally take the form of the
three most common components: *metrics*, *logs*, and *traces*. Some
monitoring systems also track and report *events*, which can represent user
interactions with an entire system, or state changes within the system itself.

*Metrics* are simply measurements taken inside a system, representing the
state of that system in a measurable way. These are almost always numeric and
tend to take the form of counters, distributions, and gauges. There are some
cases where string metrics make sense, but generally numeric metrics are used
due to the need to perform mathematical calculations on them to form statistics
and draw visualizations.

*Logs* can be thought of as append-only files that represent the state of a
single thread of work at a single point in time. These logs can be a single
string like "User pushed button X" or a structured log entry which includes
metadata such as the time the event happened, what server was processing it, and
other environmental elements.  Sometimes a system which cannot write structured
logs will produce a semi-structured string like `[timestamp] [server] message
[code]` which can be parsed after the fact, as needed. Log entries tend to be
written using a client library like log4j, structlog, bunyan, log4net, or Nlog.
Log processing can be a very reliable method of producing statistics that
can be considered trustworthy, as they can be reprocessed based on immutable
stored logs, even if the log processing system itself is buggy. Additionally,
logs can be processed in real time to produce *log-based metrics*.

*Traces* are composed of *spans*, which are used to follow an event or user
action through a distributed system. A span can show the path of a request
through one server, while another span might run in parallel, both having the
same parent span. These together form a trace, which is often visualized in a
waterfall graph similar to those used in profiling tools. This lets developers
understand time taken in a system, across many servers, queues, and network
hops. A common framework for this is
[OpenTelemetry](https://opentelemetry.io/),
which was formed from both
[OpenCensus](https://opencensus.io/)
and
[OpenTracing](https://opentracing.io/).

Metrics, logs, and traces can be reported to the monitoring system by the
server under measurement, or by an adjacent *agent* that can witness or infer
things about the system.

### Correlation

Metrics can be collected from the application, as well as from its underlying
systems, such as the JVM, guest OS, hypervisor, node OS, and the hardware
itself. Note that as you go further down in a stack, you might start conflating
metrics that are shared across workloads. For example, if a single machine
serves several applications, watching the disk usage might not correspond
directly to the system under observation. Correlating issues across applications
on a shared system, however, can help you pin down a contributing factor (such
as a slow disk). Drilling down from a single application to its underlying
system metrics, then pulling up to show all similarly affected applications can
be very powerful.

Measuring a distributed system means having observability in many places and
being able to view them all together. This might mean both a frontend and its
database, or it might mean a mobile application running on a customer's device,
a cloud load balancer, and a set of microservices. Being able to connect data
from all of these sources in one place is a fundamental requirement in modern
observability tools.

### Common pitfalls of implementing monitoring and observability

When developing a system for monitoring and observability for your
organization, you should be aware that there generally isn't a simple
plug-and-play solution. Any decent monitoring system will require a deep
understanding of each component that you want to measure, as well as direct
manipulation of the code to instrument those systems. Avoid having a single
monitoring person or dedicated team who is solely
responsible for the system. This will not only help you prevent a single point
of failure, but also increase your ability to understand and improve your system
as an entire organization. Monitoring and observability needs to be built into
the baseline knowledge of all your developers. A common pitfall here is for
the operation team, NOC, or other similar team to be the only ones allowed to
make changes to a monitoring system. This should be avoided and replaced with a
system that follows CD patterns.

A common anti-pattern in writing alerts in monitoring systems is to attempt to
enumerate all possible error conditions and write an alert for each of them. We
call this *cause-based alerting,* and you should avoid it as much as possible.
Instead, you should focus on *symptom-based alerting,* which only alerts you when
a user-facing symptom is visible or is predicted to arise soon. You should still
be able to observe non-user-facing systems, but they shouldn't be directly
alerting on-call engineers if there are no user-facing symptoms. Note that the
term *user-facing* can also include users internal to your organization.

When generating alerts, you should consider how they are delivered. Your alerts
should have multiple pathways to oncall engineers, including but not limited to:
SMS delivery, dedicated mobile apps, automated phone calls, or email. A common
pitfall is to email alerts to an entire team via an email distribution list.
This can quickly result in ignored alerts due to
[diffusion of responsibility](https://wikipedia.org/wiki/Diffusion_of_responsibility). Another common
failure is simply a poor
[signal-to-noise ratio](https://wikipedia.org/wiki/Signal-to-noise_ratio).
If too many alerts are not actionable, or result in no improvement, the team
will easily miss those alerts that are meaningful and possibly very important, a
problem known as
[alarm fatigue](https://wikipedia.org/wiki/Alarm_fatigue).
Any method to silence or suppress some set of alerts should be tracked very
carefully to ensure it is not too broad or applied too often.

When building monitoring dashboards to visualize metrics, a common mistake is
to spend a long time curating the "Perfect Dashboard". This is similar to the
cause-based alerting mistake above. In a high-functioning team, the system
under observation changes so fast that any time spent curating a dashboard will
be out of date before it is done. Instead, focusing on the ability for team
members to quickly create a dashboard or other set of visualizations that fits
their needs is important.

Failing to separate out product or executive-facing metrics such as user
acquisition rate and revenue tracking away from operational or service health
dashboards is also a common problem, as they are both very important, but
distinct. Keeping these separate is highly recommended.


## Proactive failure notification

### How to implement proactive failure notification

**Use alerting rules.** You should generate failure notifications using
specific *alerting rules.* Alerting rules define the conditions under which an
alert is generated and the notification channel for that alert. Read more about
generating alerts in
Monitoring and observability.

**Use thresholds.** Alerting rules should use thresholds for the metrics you
monitor that indicate real trouble. Monitoring thresholds trigger alerting
rules, which generate notifications when metric levels cross threshold values.

**Choose thresholds carefully.** Choose thresholds to only generate alerts when
the threshold actually predicts an issue. That is, don't arbitrarily select a
value. Generally, you should identify which value levels begin to cause
user-facing impact, and then trigger an alert notification at some percentage
before that value is crossed.

For example, you might choose to trigger an alert notification when average
response time for pages is within 20% of a threshold at which you know users
start becoming frustrated and calling support.

**Hold incident post-mortems.** When you hold post-mortems following incidents,
determine which indicators could have predicted the incident and monitor them in
the future.

**Plan a notification strategy.** If a notification requires no action or the
same action every time, you should automate the response. You should also
consider the volume of notifications for events. A deluge of notifications
during an event might be distracting rather than useful. When people are exposed
to a large number of alarms, they can become desensitized to them (a problem known
as "alert fatigue") leading to longer response times or missed alarms.
Regularly review notifications and delete those that cannot be acted upon.

### Ways to measure failure notifications

Instrumenting proactive monitoring is straightforward. The components to
capture are:

1.  The extent to which failure alerts from logging and monitoring systems
    are captured and used.
1.  The extent to which system health is proactively monitored using
    threshold warnings.
1.  The extent to which system health is proactively monitored using rate of
    change warnings.

To make sure you are capturing different aspects of your system, you should
monitor metrics in at least two different ways. For example, you might set a
metric threshold
that triggers alerts if a metric rises or falls below a value over a given time
window, and a rate of change, which triggers alerts when a metric value change
rate is higher or lower than expected.
