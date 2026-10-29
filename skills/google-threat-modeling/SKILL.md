---
name: google-threat-modeling
description: >-
  Model adversaries, trust boundaries, and risks.
---

# Google Threat Modeling

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Understanding Adversaries

### Attacker Motivations

Security adversaries are first and foremost human (at least for the time being). Therefore, we can consider the purpose of attacks through the eyes of the people who carry them out. Doing so may better equip us to understand how we should respond, both proactively (during system design) and reactively (during incidents). Consider the following attack motivations:

Fun
:   To undermine the security of a system for the sheer joy of knowing it can be done.

Fame
:   To gain notoriety for showing off technical skills.

Activism
:   To make a point or broadcast a message—typically, a political viewpoint— widely.

Financial gain
:   To make money.

### Insiders

Every organization has *insiders*: current or former employees who are trusted with internal access to systems or proprietary knowledge. *Insider risk* is the threat posed by such individuals. A person becomes an *insider threat* when they are able to perform actions that cover a wide range of malicious, negligent, or accidental scenarios that could result in harm to the organization. Insider risk is a large topic that could fill the pages of several books. To help system designers, we cover the topic briefly here by considering three general categories, as outlined in <#general_categories_of_insiders_and_exam>.

General categories of insiders and examples

| First-party insiders | Third-party insiders | Related insiders |
| --- | --- | --- |
| Employees Interns Executives Board directors | Third-party app developers Open source contributors Trusted content contributors Commercial partners Contractors Vendors Auditors | Friends Family Roommates |

### Threat modeling insider risk

Numerous frameworks exist for modeling insider risk, ranging from simple to highly topic-specific, sophisticated, and detailed. If your organization needs a simple model to get started, we have successfully used the framework in <#framework_for_modeling_insider_risk>. This model is also adaptable to a quick brainstorming session or fun card game.

Framework for modeling insider risk

| Actor/Role | Motive | Actions | Target |
| --- | --- | --- | --- |
| Engineering | Accidental | Data access | User data |
| Operations | Negligent | Exfiltration (theft) | Source code |
| Sales | Compromised | Deletions | Documents |
| Legal | Financial | Modifications | Logs |
| Marketing | Ideological | Injections | Infrastructure |
| Executives | Retaliatory | Leak to press | Services |
|  | Vanity |  | Financials |

First, establish a list of *actors/roles* present in your organization. Attempt to think of all the *actions* that may cause harm (including accidents) and potential *targets* (data, systems, etc.). You can combine items from each category to create many scenarios. Here are some examples to get you started:

- An *engineer* with access to *source code* is unsatisfied with their performance review and *retaliates* by injecting a malicious backdoor into production that steals *user data*.
- An *SRE* with access to the website’s SSL *encryption keys* is approached by a stranger and is *strongly encouraged* (for example, via threats to their family) to hand over sensitive material.
- A *financial analyst* preparing the *company financials* is working overtime and *accidentally* modifies the *final yearly revenue numbers* by a factor of 1,000%.
- An *SRE’s child* uses their parent’s laptop at home and installs a game bundled with *malware* that locks the computer and *prevents the SRE from responding* to a serious outage.

### Threat Modeling Mistakes

Sometimes people just make mistakes—to err is human. For around 40 minutes on January 31, 2009, Google Search displayed an ominous warning—“This site may harm your computer”—to every user, for every search! This warning is normally reserved for search results that link to a website that’s either compromised or hosting malware. The [root cause](https://googleblog.blogspot.com/2009/01/this-site-may-harm-your-computer-on.html) of this issue was very simple: a “/” had been implicitly (and accidentally!) added to the system’s list of sites known to install malicious software in the background, which matched every website on the planet.

Given sufficient time working with systems, everyone is likely to encounter some version of this horror story. These mistakes can be caused by working late at night without enough sleep, typos, or simply encountering unforeseen functionality in the system. When designing secure and reliable systems, remember that humans make mistakes, and consider how to prevent them. An automated check on whether “/” was added to the configuration would have prevented the aforementioned outage!

### Designing for insider risk

This book presents many design strategies for security that are applicable to protecting against insider risk and malicious “outside” attackers. When designing systems, you must consider that whoever has access to a system or its data could be any of the attacker types outlined in this chapter. Therefore, the strategies for detecting and mitigating both types of risk are similar.

We have found a few concepts to be particularly effective when thinking about insider risk:

Least privilege
:   Granting the fewest privileges necessary to perform job duties, both in terms of scope and duration of access. See Chapter 5.

Zero trust
:   Designing automated or proxy mechanisms for managing systems so that insiders don’t have broad access that allows them to cause harm. See Chapter 3.

Multi-party authorization
:   Using technical controls to require more than one person to authorize sensitive actions. See Chapter 5.

### Risk Assessment Considerations

Understanding potential adversaries, who they are, and which methods they might use can be complex and nuanced. We have found the following considerations important when assessing the risk posed by various attackers:

You may not realize you’re a target.
:   It may not be immediately obvious that your company, organization, or project is a potential target. Many organizations, despite being small or not involved in handling sensitive information, can be leveraged to carry out attacks. In September 2012, Adobe—a company best known for software that enables content creators—disclosed that [attackers had penetrated its networks](https://blogs.adobe.com/security/2012/09/inappropriate-use-of-adobe-code-signing-certificate.html) with the express intent to digitally sign their malware using the company’s official software signing certificate. This enabled the attackers to deploy malware that appeared legitimate to antivirus and other security protection software. Consider whether your organization has assets that an attacker would be interested in, either for direct gain or as part of a larger attack on someone else.

Attack sophistication is not a true predictor of success.
:   Even if an attacker has a lot of resources and skills, don’t assume that they’ll always choose the most difficult, expensive, or esoteric means to achieve their goals. Generally speaking, attackers choose the simplest and most cost-effective methods of compromising a system that meet their goals. For example, some of the most prominent and impactful intelligence gathering operations rely on basic [*phishing*](https://googleblog.blogspot.com/2011/06/ensuring-your-information-is-safe.html)—tricking a user into handing over their password. For this reason, when designing your systems, be sure to cover the simple basics of security (like using two-factor authentication) before worrying about esoteric and exotic attacks (like firmware backdoors).

Don’t underestimate your adversary.
:   Don’t assume that an adversary can’t procure the resources to carry out an expensive or difficult attack. Consider carefully how much your adversary is willing to spend. The extraordinary tale of the NSA implanting backdoors in Cisco hardware by intercepting shipments en route to customers illustrates the lengths that well-funded and talented attackers will go to achieve their goals. However, keep in mind that these types of cases are very much the exception rather than the norm.

Attribution is hard.
:   In March 2016, researchers uncovered a new type of ransomware—a malicious program that renders data or systems unavailable until the victim pays a ransom—which they named Petya. Petya appeared to be financially motivated. A year later, researchers discovered a new piece of malware that shared many elements of the original Petya program. Dubbed [NotPetya](https://www.wired.com/story/notpetya-cyberattack-ukraine-russia-code-crashed-the-world/), the new malware spread globally very quickly, but was primarily found on systems in Ukraine on the eve of a Ukrainian holiday. To deliver NotPetya, attackers compromised a company that made products explicitly for the Ukrainian market and abused their software distribution mechanism to infect victims. Some researchers believe that this attack was carried out by a Russian state-sponsored actor in order to target Ukraine.

This example shows that motivated attackers can hide their motives and identity in creative ways—in this case, by disguising themselves as something potentially more benign. Since the identity and intent of attackers may not always be well understood, we recommend that you focus on how attackers work (their TTPs) before worrying about who they are specifically.

Attackers aren’t always afraid of being caught.
:   Even if you manage to track an attacker’s location and identity, the criminal system (especially internationally) may make it difficult to hold them legally accountable for their actions. This is especially true for nation-state actors working directly for a government that may be unwilling to extradite them for criminal prosecution.


## Design for Understandability

### Security boundaries and threat models

A trusted computing base’s size and shape will depend on the security property you want to guarantee and the architecture of your system. You can’t just draw a dashed line around a component of your system and call it a TCB. You have to think about the component’s interface, and the ways in which it might implicitly trust the rest of the system.

Suppose our application allows users to view and update their shipping addresses. Since the purchasing backend handles shipping addresses, that backend needs to expose an RPC method that allows the web frontend to retrieve and update a user’s shipping address.

If the purchasing backend allows the frontend to obtain *any* user’s shipping address, an attacker who compromises the web frontend can use this RPC method to access or modify sensitive data for any and all users. In other words, if the purchasing backend trusts the web frontend more than it trusts a random third party, then the web frontend is part of the TCB.

Alternatively, the purchasing backend could require the frontend to provide a so-called [*end-user context ticket* (EUC)](https://cloud.google.com/security/beyondprod/#google%E2%80%99s_internal_security_services) that authenticates a request in the context of a specific external user request. The EUC is an internal short-term ticket that’s minted by a central authentication service in exchange for an external-facing credential, such as an authentication cookie or a token (for example, OAuth2) associated with a given request. If the backend provides data only in response to requests with a valid EUC, an attacker who compromises the frontend does *not* have complete access to the purchasing backend, because they can’t get EUCs for any arbitrary user. At the worst, they could obtain sensitive data about users who are actively using the application during the attack.

To provide another example that illustrates how TCBs are relative to the threat model under consideration, let’s think about how this architecture relates to the security model of the web platform. In this security model, a *web origin* (the fully qualified hostname of the server, plus the protocol and optional port) represents a trust domain: JavaScript running in the context of a given origin can observe or modify any information present in or available to that context. In contrast, browsers restrict access between content and code across different origins based on rules referred to as the *same-origin policy*.

Our web frontend might serve its entire UI from a single web origin, such as *https://widgets.example.com*. This means that, for example, a malicious script injected into our origin via an XSS vulnerability in the catalog display UI can access a user’s profile information, and might even be able to “purchase” items in the name of that user. Thus, in a web security threat model, TCBAddressData again includes the entire web frontend.
