# Agent Skills — Open Standard Overview & Specification

*Sources: https://agentskills.io/ + https://agentskills.io/specification*
*Fetched: 2026-04-27*
*Tier: 1 (citable)*

---

> The canonical, open-standard specification for the Agent Skills format. Originally developed by Anthropic, released as an open standard.

---

## Part 1: Overview (from agentskills.io home)


A standardized way to give AI agents new capabilities and expertise.
## [​](#what-are-agent-skills)What are Agent Skills?

Agent Skills are a lightweight, open format for extending AI agent capabilities with specialized knowledge and workflows.
At its core, a skill is a folder containing a `SKILL.md` file. This file includes metadata (`name` and `description`, at minimum) and instructions that tell an agent how to perform a specific task. Skills can also bundle scripts, reference materials, templates, and other resources.

```
my-skill/
├── SKILL.md # Required: metadata + instructions
├── scripts/ # Optional: executable code
├── references/ # Optional: documentation
├── assets/ # Optional: templates, resources
└── ... # Any additional files or directories

```

## [​](#why-agent-skills)Why Agent Skills?

Agents are increasingly capable, but often don’t have the context they need to do real work reliably. Skills solve this by packaging procedural knowledge and company-, team-, and user-specific context into portable, version-controlled folders that agents load on demand. This gives agents:

- **Domain expertise**: Capture specialized knowledge — from legal review processes to data analysis pipelines to presentation formatting — as reusable instructions and resources.

- **Repeatable workflows**: Turn multi-step tasks into consistent, auditable procedures.

- **Cross-product reuse**: Build a skill once and use it across any skills-compatible agent.

## [​](#how-do-agent-skills-work)How do Agent Skills work?

Agents load skills through **progressive disclosure**, in three stages:

1. 
**Discovery**: At startup, agents load only the name and description of each available skill, just enough to know when it might be relevant.

2. 
**Activation**: When a task matches a skill’s description, the agent reads the full `SKILL.md` instructions into context.

3. 
**Execution**: The agent follows the instructions, optionally executing bundled code or loading referenced files as needed.

Full instructions load only when a task calls for them, so agents can keep many skills on hand with only a small context footprint.

## [​](#where-can-i-use-agent-skills)Where can I use Agent Skills?

Agent Skills are supported by a large number of AI tools and agentic clients — see the [Client Showcase](/clients) to explore some of them!

## [​](#open-development)Open development

The Agent Skills format was originally developed by [Anthropic](https://www.anthropic.com/), released as an open standard, and has been adopted by a growing number of agent products. The standard is open to contributions from the broader ecosystem.
Come join the discussion on [GitHub](https://github.com/agentskills/agentskills) or [Discord](https://discord.gg/MKPE9g8aUy)!

## [​](#get-started-with-agent-skills)Get started with Agent Skills

## Quickstart
Create your first Agent Skill and see it in action.
## Specification
The complete format specification for Agent Skills.

---

## Part 2: Specification (from agentskills.io/specification)


The complete format specification for Agent Skills.
## [​](#directory-structure)Directory structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md # Required: metadata + instructions
├── scripts/ # Optional: executable code
├── references/ # Optional: documentation
├── assets/ # Optional: templates, resources
└── ... # Any additional files or directories

```

## [​](#skill-md-format)`SKILL.md` format

The `SKILL.md` file must contain YAML frontmatter followed by Markdown content.

### [​](#frontmatter)Frontmatter

FieldRequiredConstraints`name`YesMax 64 characters. Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen.`description`YesMax 1024 characters. Non-empty. Describes what the skill does and when to use it.`license`NoLicense name or reference to a bundled license file.`compatibility`NoMax 500 characters. Indicates environment requirements (intended product, system packages, network access, etc.).`metadata`NoArbitrary key-value mapping for additional metadata.`allowed-tools`NoSpace-separated string of pre-approved tools the skill may use. (Experimental)

## 
**Minimal example:**SKILL.md

```
---
name: skill-name
description: A description of what this skill does and when to use it.
---

```
**Example with optional fields:**SKILL.md

```
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
license: Apache-2.0
metadata:
 author: example-org
 version: "1.0"
---

```

#### [​](#name-field)`name` field

The required `name` field:

- Must be 1-64 characters

- May only contain unicode lowercase alphanumeric characters (`a-z`) and hyphens (`-`)

- Must not start or end with a hyphen (`-`)

- Must not contain consecutive hyphens (`--`)

- Must match the parent directory name

## 
**Valid examples:**

```
name: pdf-processing

```

```
name: data-analysis

```

```
name: code-review

```
**Invalid examples:**

```
name: PDF-Processing # uppercase not allowed

```

```
name: -pdf # cannot start with hyphen

```

```
name: pdf--processing # consecutive hyphens not allowed

```

#### [​](#description-field)`description` field

The required `description` field:

- Must be 1-1024 characters

- Should describe both what the skill does and when to use it

- Should include specific keywords that help agents identify relevant tasks

## 
**Good example:**

```
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.

```
**Poor example:**

```
description: Helps with PDFs.

```

#### [​](#license-field)`license` field

The optional `license` field:

- Specifies the license applied to the skill

- We recommend keeping it short (either the name of a license or the name of a bundled license file)

## 
**Example:**

```
license: Proprietary. LICENSE.txt has complete terms

```

#### [​](#compatibility-field)`compatibility` field

The optional `compatibility` field:

- Must be 1-500 characters if provided

- Should only be included if your skill has specific environment requirements

- Can indicate intended product, required system packages, network access needs, etc.

## 
**Examples:**

```
compatibility: Designed for Claude Code (or similar products)

```

```
compatibility: Requires git, docker, jq, and access to the internet

```

```
compatibility: Requires Python 3.14+ and uv

```

Most skills do not need the `compatibility` field.

#### [​](#metadata-field)`metadata` field

The optional `metadata` field:

- A map from string keys to string values

- Clients can use this to store additional properties not defined by the Agent Skills spec

- We recommend making your key names reasonably unique to avoid accidental conflicts

## 
**Example:**

```
metadata:
 author: example-org
 version: "1.0"

```

#### [​](#allowed-tools-field)`allowed-tools` field

The optional `allowed-tools` field:

- A space-separated string of tools that are pre-approved to run

- Experimental. Support for this field may vary between agent implementations

## 
**Example:**

```
allowed-tools: Bash(git:*) Bash(jq:*) Read

```

### [​](#body-content)Body content

The Markdown body after the frontmatter contains the skill instructions. There are no format restrictions. Write whatever helps agents perform the task effectively.
Recommended sections:

- Step-by-step instructions

- Examples of inputs and outputs

- Common edge cases

Note that the agent will load this entire file once it’s decided to activate a skill. Consider splitting longer `SKILL.md` content into referenced files.

## [​](#optional-directories)Optional directories

### [​](#scripts/)`scripts/`

Contains executable code that agents can run. Scripts should:

- Be self-contained or clearly document dependencies

- Include helpful error messages

- Handle edge cases gracefully

Supported languages depend on the agent implementation. Common options include Python, Bash, and JavaScript.

### [​](#references/)`references/`

Contains additional documentation that agents can read when needed:

- `REFERENCE.md` - Detailed technical reference

- `FORMS.md` - Form templates or structured data formats

- Domain-specific files (`finance.md`, `legal.md`, etc.)

Keep individual [reference files](#file-references) focused. Agents load these on demand, so smaller files mean less use of context.

### [​](#assets/)`assets/`

Contains static resources:

- Templates (document templates, configuration templates)

- Images (diagrams, examples)

- Data files (lookup tables, schemas)

## [​](#progressive-disclosure)Progressive disclosure

Agents load skills *progressively*, pulling in more detail only as a task calls for it. Skills should be structured to take advantage of this:

1. **Metadata** (~100 tokens): The `name` and `description` fields are loaded at startup for all skills

2. **Instructions** (< 5000 tokens recommended): The full `SKILL.md` body is loaded when the skill is activated

3. **Resources** (as needed): Files (e.g. those in `scripts/`, `references/`, or `assets/`) are loaded only when required

Keep your main `SKILL.md` under 500 lines. Move detailed reference material to separate files.

## [​](#file-references)File references

When referencing other files in your skill, use relative paths from the skill root:
SKILL.md

```
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py

```

Keep file references one level deep from `SKILL.md`. Avoid deeply nested reference chains.

## [​](#validation)Validation

Use the [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) reference library to validate your skills:

```
skills-ref validate ./my-skill

```

This checks that your `SKILL.md` frontmatter is valid and follows all naming conventions.
