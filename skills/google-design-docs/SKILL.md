---
name: google-design-docs
description: >-
  Draft system design docs and assess tradeoffs.
---

# Google Engineering Design Documents

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Design Tradeoffs

### Design Objectives and Requirements

The feature requirements for your product will tend to have significantly different characteristics than your requirements for security and reliability. Let’s take a closer look at the types of requirements you’ll face when designing a product.

### Feature Requirements

*Feature requirements*, also known as *functional requirements*, identify the primary function of a service or application and describe how a user can accomplish a particular task or satisfy a particular need. They are often expressed in terms of *use cases*, *user stories*, or [*user journeys*](https://landing.google.com/sre/workbook/chapters/implementing-slos/#modeling-user-journeys)—sequences of interactions between a user and the service or application. *Critical requirements* are the subset of feature requirements that are essential to the product or service. If a design does not satisfy a critical requirement or critical user story, you don’t have a viable product.

Feature requirements are typically the primary drivers for your design decisions. After all, you’re trying to build a system or service that satisfies a particular set of needs for the group of users you have in mind. You often have to make tradeoff decisions between the various requirements. With that in mind, it is useful to distinguish critical requirements from other feature requirements.

Usually, a number of requirements apply to the entire application or service. These requirements often don’t show up in user stories or individual feature requirements. Instead, they’re stated once in centralized requirements documentation, or even implicitly assumed. Here's an example:

All views/pages of the application’s web UI must:
:   - Follow common visual design guidelines
    - Adhere to accessibility guidelines
    - Have a footer with links to privacy policy and ToS (Terms of Service)

### Nonfunctional Requirements

Several categories of requirements focus on general attributes or behaviors of the system, rather than specific behaviors. These *nonfunctional requirements* are relevant to our focus—security and reliability. For example:

- What are the exclusive circumstances under which someone (an external user, customer-support agent, or operations engineer) may have access to certain data?
- What are the [service level objectives (SLOs)](https://landing.google.com/sre/sre-book/chapters/service-level-objectives/) for metrics such as uptime or 95th-percentile and 99th-percentile response latency? How does the system respond under load above a certain threshold?

When balancing requirements, it can be helpful to simultaneously consider requirements in areas beyond the system itself, since choices in those areas can have significant impact on core system requirements. Those broader areas include the following:

Development efficiency and velocity
:   Given the chosen implementation language, application frameworks, testing processes, and build processes, how efficiently can developers iterate on new features? How efficiently can developers understand and modify or debug existing code?

### Features Versus Emergent Properties

Feature requirements usually exhibit a fairly straightforward connection between the requirements, the code that satisfies those requirements, and tests that validate the implementation. For example:

Specification
:   A user story or requirement might stipulate how a signed-in user of an application can view and modify the personal data associated with their user profile (such as their name and contact information).

### Example: Google Design Document

Google uses a design document template to guide new feature design and to collect feedback from stakeholders before starting an engineering project.

The template sections pertaining to reliability and security considerations remind teams to think about the implications of their project and kick off the production readiness or security review processes if appropriate. Design reviews sometimes happen multiple quarters before engineers officially start thinking about the launch stage.

### Google’s Design Document Template

Here are the reliability- and security-related sections of the Google design document template:

Scalability
:   How does your system scale? Consider both data size increase (if applicable) and traffic increase (if applicable).

Consider the current hardware situation: adding more resources might take much longer than you think, or might be too expensive for your project. What initial resources will you need? You should plan for high utilization, but be aware that using more resources than you need will block expansion of your service.

Redundancy and reliability
:   Discuss how the system will handle local data loss and transient errors (e.g., temporary outages), and how each affects your system.

    Which systems or components require data backup? How is the data backed up? How is it restored? What happens between the time data is lost and the time it’s restored?
:   In the case of a partial loss, can you keep serving? Can you restore only missing portions of your backups to your serving data store?

Dependency considerations
:   What happens if your dependencies on other services are unavailable for a period of time?

    Which services must be running in order for your application to start? Don’t forget subtle dependencies like resolving names using DNS or checking the local time.
:   Are you introducing any dependency cycles, such as blocking on a system that can’t run if your application isn’t already up? If you have doubts, discuss your use case with the team that owns the system you depend on.

Data integrity
:   How will you find out about data corruption or loss in your data stores?

    What sources of data loss are detected (user error, application bugs, storage platform bugs, site/replica disasters)?
:   How long will it take to notice each of these types of losses?

What is your plan to recover from each of these types of losses?

SLA requirements
:   What mechanisms are in place for auditing and monitoring the service level guarantees of your application?

How can you guarantee the stated level of reliability?

Security and privacy considerations
:   Our systems get attacked regularly. Think about potential attacks relevant for this design and describe the worst-case impact it would have, along with the countermeasures you have in place to prevent or mitigate each attack.

    List any known vulnerabilities or potentially insecure dependencies.
:   If, for some reason, your application doesn’t have security or privacy considerations, explicitly state so and why.

Once your design document is finalized, file a quick security design review. The design review will help avoid systemic security issues that can delay or block your final security review.

### Cost of Adding Reliability and Security to Existing Systems

The emergent nature of security and reliability means that design choices related to these considerations are often fairly fundamental, and similar in nature to basic architectural choices like whether to use a relational or NoSQL database for storage, or whether to use a monolithic or microservices architecture. It’s usually difficult to “bolt on” security and reliability to an existing system that wasn’t designed from the outset with these concerns in mind. If a system lacks well-defined and understandable interfaces between components and contains a tangled set of dependencies, it likely will have lower availability and be prone to bugs with security consequences (see Chapter 6). No amount of testing and tactical bug-fixing will change that.

Accommodating security and reliability requirements in an existing system often requires significant design changes, major refactorings, or even partial rewrites, and can become very expensive and time-consuming. Furthermore, such changes might have to be made under time pressure in response to a security or reliability incident—but making significant design changes to a deployed system in a hurry comes with a significant risk of introducing additional flaws. It’s therefore important to consider security and reliability requirements and corresponding design tradeoffs from the early planning phases of a software project. These discussions should involve security and SRE teams, if your organization has them.

This section presents an example that illustrates the kinds of tradeoffs you might have to consider. Some parts of this example delve quite deeply into technical details, which aren’t necessarily important in and of themselves. All of the compliance, regulatory, legal, and business considerations that go into designing payment processing systems and their operation aren’t important for this example either. Instead, the purpose is to illustrate the complex interdependencies between requirements. In other words, the focus isn’t on the details about protecting credit card numbers, but rather the thought process that goes into designing a system with complex security and reliability requirements.

### Initial Velocity Versus Sustained Velocity

There’s a natural tendency, especially in smaller teams, to defer security and reliability concerns until some point in the future (“We’ll add in security and worry about scaling after we have some customers”). Teams commonly justify ignoring security and reliability as early and primary design drivers for the sake of “velocity”—they’re concerned that spending time thinking about and addressing these concerns will slow development and introduce unacceptable delays into their first release cycle.

It’s important to make a distinction between *initial velocity* and *sustained velocity.* Choosing to not account for critical requirements like security, reliability, and maintainability early in the project cycle may indeed increase your project’s velocity early in the project’s lifetime. However, experience shows that doing so also usually *slows you down significantly* later. The late-stage cost of retrofitting a design to accommodate requirements that manifest as emergent properties can be *very* substantial. Furthermore, making invasive late-stage changes to address security and reliability risks can in itself introduce even more security and reliability risks. Therefore, it’s important to embed security and reliability in your team culture early on (for more on this topic, see Chapter 21).

More generally, you can choose to prioritize initial project velocity above all else—you can develop the first iteration of your web app without tests, and with a release process that amounts to copying tarballs to production hosts. You’ll probably get your first demo out relatively quickly, but by your third release, your project will quite possibly be behind schedule and saddled with technical debt.

- Unit and integration test coverage robust enough to ensure an acceptably low risk of defects for production releases, without requiring major human release qualification work
- A CI/CD pipeline that is itself reliable
- A frequently exercised, reliable infrastructure for staggered production rollouts and rollbacks
- A software architecture that permits [decoupled rollouts](https://landing.google.com/sre/workbook/chapters/configuration-design/) of code and configurations (e.g., “feature flags”)

This investment is typically modest when made early in a product’s lifecycle, and it requires only incremental effort by developers to maintain good test coverage and “green builds” on an ongoing basis. In contrast, a development workflow with poor test automation, reliance on manual steps in deployment, and long release cycles tends to eventually bog down a project as it grows in complexity. At that point, retrofitting test and release automation tends to require a lot of work all at once and might slow down your project even more. Furthermore, tests retrofitted to a mature system can sometimes fall into the trap of exercising the current buggy behavior more than the correct, intended behavior.

When it comes to making security-focused design choices that contribute to sustained velocity, we recommend choosing a framework and workflow that provide secure-by-construction defense against relevant classes of vulnerabilities. This choice can drastically reduce, or even eliminate, the risk of introducing such vulnerabilities during ongoing development and maintenance of your application’s codebase (see Chapters Chapter 6 and Chapter 12). This commitment generally doesn’t involve significant up-front investment—rather, it entails an incremental and typically modest ongoing effort to adhere to the framework’s constraints. In return, you drastically reduce your risk of unplanned system outages or security response fire drills throwing deployment schedules into disarray. Additionally, your release-time security and production readiness reviews are much more likely to go smoothly.
