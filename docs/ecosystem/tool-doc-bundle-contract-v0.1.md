# Tool Documentation Bundle Contract v0.1

This document defines the expected documentation bundle for each supported tool or wrapper-capable feature in the MyAI ecosystem.

## Purpose

Every supported tool should be:

- understandable by humans
- understandable by AI
- easy to install and validate
- easy to invoke directly
- easy to invoke through wrappers

The documentation bundle is the bridge between the catalog entry and actual usage.

## Bundle structure

Recommended layout:

```text
docs/tools/<tool-id>/
  README.md
  SKILLS.md
  HELP.md
  QUICKSTART.md
```

## 1. README.md

Audience:

- human operators
- developers
- admins

Should include:

- what the tool does
- why it is useful in MyAI
- install/setup prerequisites
- wrapper command if one exists
- direct command examples
- common workflows
- common failure modes

## 2. SKILLS.md

Audience:

- AI agents
- agent planners
- automation layers

Should include:

- canonical `tool_id`
- safe/default invocation patterns
- expected input/output style
- approval/risk caveats
- preferred use cases
- anti-patterns / what not to do

Example sections:

- purpose
- supported operations
- wrapper usage
- raw usage
- guardrails
- examples

## 3. HELP.md

Audience:

- humans and AI

Should include:

- normalized `--help` breakdown
- key flags and meanings
- typical parameter combinations
- examples by scenario

This does not have to be a literal full dump of `--help` if that is too noisy. It should be curated where useful.

## 4. QUICKSTART.md

Audience:

- first-time users
- setup/testing flows

Should include:

- minimum steps to get a successful result
- one or two simple example commands
- wrapper vs direct command examples
- validation checks

## Optional docs

If useful later:

- `INSTALL.md`
- `TROUBLESHOOTING.md`
- `EXAMPLES.md`
- `OUTPUTS.md`

## Bundle metadata

Each bundle should map cleanly back to the tool catalog contract:

- `tool_id`
- wrapper command
- implementation(s)
- risk/approval mode
- supported profiles or role affinities

## AI-oriented requirements

For `SKILLS.md`, include at minimum:

- stable tool name
- deterministic wrapper command
- input expectations
- output expectations
- known side effects
- approval requirements
- examples

This allows the file to function similarly to `skills.md` style instruction support.

## Human-oriented requirements

For `README.md` and `QUICKSTART.md`, include:

- plain-language explanation
- install/getting started path
- direct command examples
- wrapper command examples
- troubleshooting hints

## Wrapper command coverage

If a wrapper exists, docs should include both:

### Direct invocation

Example:

```bash
magick input.png -resize 1080x1080 output.png
```

### Wrapped invocation

Example:

```bash
myai image resize --input input.png --width 1080 --height 1080 --output output.png
```

## Output guidance

Where relevant, document:

- output file types
- output schema
- stdout/stderr behavior
- generated artifacts
- failure codes or patterns

## Suggested generation pipeline

Eventually, installer modules or wrapper registration should be able to generate or update parts of the docs bundle from:

- tool catalog metadata
- runtime capability inspection
- `--help` extraction
- curated examples

This should not fully replace human curation, but it can reduce duplication.

## Relationship to installer modules

When a tool is enabled or installed, the platform should aim to:

1. validate the tool
2. register it in the runtime registry
3. ensure its docs bundle exists or is refreshed

## Minimum standard for “supported” tools

A tool should ideally not be marked as broadly supported unless it has at least:

- a catalog entry
- a README
- a SKILLS file
- a quickstart path

## Notes

- This contract is intended to make tool usage coherent across UI, CLI, AIDE, and companion flows.
- It also supports your goal of making tools discoverable in a familiar README/cheatsheet style for both people and AI.
