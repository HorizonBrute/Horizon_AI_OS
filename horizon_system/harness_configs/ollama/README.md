# Ollama Harness Config

Ollama uses Modelfiles to define model behavior and system prompts.

## AIOS integration

To run an Ollama model with AIOS context awareness, create a Modelfile that:
1. Inherits from your chosen base model (e.g., `FROM llama3`)
2. Sets a SYSTEM prompt referencing the agent instructions from `agents.md`

A template Modelfile is provided in this directory.

## Status

Community contribution welcome. See `horizon_system/license/CONTRIBUTING.md`.
