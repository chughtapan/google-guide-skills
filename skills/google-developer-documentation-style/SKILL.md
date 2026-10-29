---
name: google-developer-documentation-style
description: >-
  Edit prose, UI terms, links, and procedures.
---

# Google Developer Documentation Style

Apply this guidance to the actual project. Repository requirements and newer authoritative guidance take precedence.

## Highlights

### Tone and content

- Be conversational and friendly without being
  frivolous.
- Don't pre-announce anything in
  documentation.
- Use descriptive link text.
- Write accessibly.
- Write for a global audience.

### Language and grammar

- Use second person: "you" rather than
  "we."
- Use active voice: make clear who's performing
  the action.
- Use standard American spelling and
  punctuation.
- Put conditions before instructions,
  not after.
- For usage and spelling of specific words, see
  the word list.

### Formatting, punctuation, and organization

- Use sentence case for document
  titles and section headings.
- Use numbered lists for sequences.
- Use bulleted lists for most other lists.
- Use description lists for pairs of related
  pieces of data.
- Use serial commas.
- Put code-related text in code font.
- Put UI elements in bold.
- Use unambiguous date formatting.


## Voice and tone

### Some things to avoid where possible

- Buzzwords or
  technical jargon.
- Being too cutesy.
- Avoid figurative language,
  which includes metaphors and ableist language.
- Placeholder phrases like *please note* and *at this time.*
- Choppy or long-winded sentences.
- Starting all sentences with the same phrase (such as *You can* or *To
  do*).
- Current pop-culture references.
- Exclamation marks. In general, avoid exclamation points. See Specific guidance on exclamation points.
- Wackiness, zaniness, and goofiness.
- Phrasing that denigrates or insults any group of people.
- Phrasing in terms of *let's* do something.
- Using phrases like *simply*, *It's that simple*, *It's easy*, or *quickly* in a
  procedure.
- Internet slang, or other internet
  abbreviations such as *tl;dr* or
  *ymmv*.

### Some techniques and approaches to consider

- If you're having trouble expressing something, step back and ask yourself,
  "What am I trying to say?" Often, the answer you give yourself reveals what you
  should be saying in the document.
- If you're uncertain about your phrasing or tone, ask a colleague to take a
  look.
- Try reading parts of your document out loud, or at least mouthing the
  words. Does it sound natural? Not every sentence has to sound natural when
  spoken; these are written documents. But if you come across a sentence that's
  awkward or confusing when spoken, consider whether you can make it more
  conversational.
- Use transitions between sentences. Phrases like *Though* or *This way* can
  make paragraphs less stilted. (Then again, sometimes transitions like *However*
  or *Nonetheless* can make paragraphs more stilted.)
- Even if you're having trouble hitting the right tone, make sure you're
  communicating useful information in a clear and direct way; that's the most
  important part.


## Code in text

### Some specific items to put in code font

The following table includes items that should be in code font, but it's not an exhaustive
list:

| Item | Recommended |
| --- | --- |
| Attribute names and values | The `imageURL` attribute contains the path for the image file that you can open in a browser—for example, `https://www.example.com/images/product.jpg`.  You can create a VM instance using the `e2-highcpu-16` machine type in the `us-central1-a` region. |
| Class names | The `SnapshotDiskOperator` class includes the `generate_snapshot_name` method. |
| Command output | The output is similar to the following:     ```         Found sysprep-specialize-script-ps1 in metadata.         ...         Finished running specialize scripts. ``` |
| Command-line utility names, such as `gcloud`, `gsutil`, `kubectl`, and `bq` | You can use the `kubectl` tool to define a network policy. |
| Data types | Nested data is represented as a `STRUCT` type. |
| Database elements (such as row and column names) | The query extracts the `month`, `julianday`, and `dayofweek` values from the `datetime` and `timestamp` columns. |
| Defined (constant) values for an element or attribute | The constant `city` has the value `"San Francisco"`. |
| [DNS record types](https://wikipedia.org/wiki/List_of_DNS_record_types) | Create a DNS `AAAA` record in your public DNS zone that points to the IP address of the load balancer. |
| Element names (HTML and XML) | The `script` and `df-messenger` HTML elements should be in the `body` element of your page.  A C-CDA document contains a header and a body enclosed within a `ClinicalDocument` XML element.  When you refer to an element name, don't put angle brackets (`<>`) around the element name. |
| Enum (enumerator) names | Generated from the protobuf enum `BOOL = 1;`. |
| Environment variable names | Set the `CHROME_REMOTE_DESKTOP_DEFAULT_DESKTOP_SIZES` environment variable to include the resolution of your monitor. |
| Filenames, filename extensions (if used), and paths | Open the `pg_hba.conf` file, which is typically in the `/etc/postgresql/13/main` directory. |
| Folders and directories | The configuration information for the reader deployment is in the `opentsdb-read.yaml.tpl` file in the `deployments` folder of the guide repository. |
| [HTTP content-type](https://www.w3.org/Protocols/rfc1341/4_Content-Type.html) values | The value of the `Content-Type` header value is required and must be set to `application/fhir+json` as defined in the FHIR specification. |
| HTTP status codes | The HTTP `500 Internal Server Error` status code indicates that the server encountered an unexpected condition that prevented it from fulfilling the request. |
| HTTP verbs | To specify image content directly using a local image file, you can use a `POST` request. |
| IAM role names | Grant the new service account the `roles/cloudfunctions.invoker` IAM role for the `trace` function. |
| IP addresses | The other nodes of the cluster should contact this host on IP address `10.10.10.10.` |
| Language keywords | The SQL statement contains the dataset table name after the `FROM` keyword in the format of `PROJECT_NAME.DATASET.TABLE_NAME`. |
| Method and function names | The `ST_GEOPOINT` function uses the longitude and latitude of the Colosseum in Rome.  To fetch the status of the job, call the `get_job_status` method. |
| Namespace aliases | Use Config Sync to apply the package only to the `default` namespace. |
| Placeholder variables | Replace `SUBNETWORK_NAME` with the resource ID of the private subnet that you want the blueprint to use. |
| Package names | The Beautiful Soup library for parsing web pages is distributed as the `beautifulsoup4` package. |
| Port numbers | Each member Pod must have a container that's listening on TCP port `50000`. |
| Query parameter names and values | If you want to return all contents under a directory, use the `recursive=true` query parameter with your request. |
| Strings (such as URLs or domain names) that are used in commands and code | In IAM, a condition can specify a page that only Human Resources admins can access—for example, `https://hr.example.com`.  The `logID` field includes the domain `corpaudits.example.com`. |
| Text input | In the **Key name** field, enter `config-management`. |
| UI elements that are rendered based on previously entered text (such as a server or instance name) | From the **Server name** list, select **`my-sql-cluster1`**.  Click **`my-instance`**.  If a code-formatted element appears in UI, add bold as well. For more information, see Code in UI elements. |

Generally, don't put quotation marks around code unless the quotation marks
are part of the code.


## UI elements and interaction

### Focus on the task

When practical, state instructions in terms of what the reader
should accomplish, rather than focusing on the widgets and gestures.
By avoiding reference to UI elements, you help the reader understand
the purpose of an instruction, and it can help future-proof
procedures.

Recommended: Refresh the page.

Recommended: Expand the **Advanced options**
section.

### Format names of UI elements

When referring to any UI element by name, put its name in bold, using the
`b` element in HTML or `**` in Markdown. This
includes names for buttons, menus, dialogs, windows, list items, or any other
feature on the page that has a visible name. Don't use code font for UI elements,
unless it's an element that meets the requirements for code font.
In that case, use both code font and bold.

**Note**: The reason for using the [`b`
element](https://html.spec.whatwg.org/multipage/semantics.html#the-b-element) is that in modern HTML, `b` connotes text to which
you want to draw visual attention, whereas the [`strong`
element](https://html.spec.whatwg.org/multipage/semantics.html#the-strong-element) indicates strong importance.

Don't make an official feature name or product name bold, except when it
directly refers to an element on the page that uses the name (such as a window
title or button name).


## Cross-references and linking

### Write descriptive link text

For the link text itself, use short, unique, descriptive phrases that provide
context for the material that you're linking to.

Effective link text helps to improve accessibility and scannability. Different
readers experience links differently. For example, users of screen reader
software often jump from one link to the next without reading the words in
between. Other readers visually scan a document to find relevant links.

Sometimes you have to rework a sentence to include a phrase that makes good
link text.

### Avoid vague link text

Write link text that makes sense without the surrounding text.
Don't use phrases such as *this document*, *this article*, or *click here*.


## Procedures

### Summary of guidelines for writing procedures

| Guidance | Recommended | Not recommended |
| --- | --- | --- |
| Make sure that the first sentence in a procedural step includes an imperative verb. | Clone the repository that contains the sample data. | You need the project ID later in this document. Retrieve the project ID. |
| Use complete sentences. |  |  |
| Use parallel structure and consistent verb form. | Download the service account key to your local machine. Click **More**, and then click **Download**. | Download the service account key to your local machine by clicking **More** and then clicking **Download** file. |
| For an optional step, type *Optional:* as the first word of the step. | Optional: Type an arbitrary string... | (Optional) Type an arbitrary string... |
| Set the context (such as a tool or an environment) in which the reader performs a procedure.  If there are multiple headings associated with a set of procedures, restate the context of the procedure in the first step, even if the context is the same as in the previous procedure. | In Cloud Shell, connect to the development cluster.  In the Google Cloud console, go to the **BigQuery** page. |  |
| Write in the order that the reader needs to follow. State the location of the action before stating the action. | In Google Docs, click **File > New > Document**.  In the Google Cloud console, go to the **Monitoring** page. | Click **File > New > Document** in Google Docs.  Go to the **Monitoring** page in the Google Cloud console. |
| State the purpose or goal of the action before stating the action. | To start a new document, click **File > New > Document**. | Click **File > New > Document** to start a new document. |
| Don't use directional language to orient the reader, such as *above*, *below*, or *right-hand side*. This type of language doesn't work well for accessibility or for localization. If a UI element is hard to find, provide a screenshot.  For information about documenting icons, see Buttons and icons. | Click menu**Menu**.  In the preceding diagram,...  In the following diagram,... | Click the button with three lines.  In the above diagram, ...  In the diagram below, ... |
| Don't use *please*. | To open a document, click **File > Open**. | To open a document, please click **File > Open**. |
| Avoid using *run the following command* to introduce code. Instead, focus on what the command does. | In Cloud Shell, deploy the load generator:...  Define a firewall rule to allow internal traffic:... | In Cloud Shell, deploy the load generator by running the following command:...  Run the following command:... |
| If the reader must press **Enter** after a step, then include that instruction as part of the step. | Click the search box, type `custom function`, and then press **Enter**. | 1. Click the search box and type `custom function`. 2. Press **Enter**. |
| Don't include keyboard shortcuts. | Copy the command, and then paste it... | Press Ctrl+C, and then press Ctrl+V... |
| When there's more than one way to do something, give only the best way. Giving alternate ways can confuse readers. |  |  |
| If your procedure includes code samples, see how to format  code samples. |  |  |
| If your procedure includes commands, see how to format  commands. |  |  |
| Ensure that the reader has the information that they need in order to prepare for the task ahead of time. Having information in advance supports task management, executive functioning, memory, and emotional regulation. | The following hardware and software are required:... |  |
| Include as few steps as possible to complete the task. Limit interruptions in the path. |  |  |
| Focus on one reader decision at a time. Separate each instruction by making each instruction a separate list item. |  |  |
