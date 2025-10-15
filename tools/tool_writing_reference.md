# OpenWebUI Tool Writing Reference

## Purpose of Tools

- Tools extend the abilities of LLMs, allowing them to interact with real-world data (e.g., weather updates, stock prices).
- They act as plugins that the LLM can call during conversations.

## Basic Structure

- Tools should expose top-level functions that the OpenWebUI can call directly.
- Each function should have clear parameters and return values.

## Metadata

- Include metadata at the top of the file for documentation and compatibility:

  ```bashpython
  """
  # Tool Name - Description
  title: Tool Name
  author: Author Name
  version: 1.0.0
  description: Brief description of the tool.
  """
  ```

## Error Handling

- Ensure robust error handling to provide meaningful feedback when something goes wrong.

## Testing and Debugging

- Test tools in isolation to ensure they work as expected before integrating them into OpenWebUI.

## Examples of Tools

- Real-time weather predictions.
- Stock price retrievers.
- Flight tracking information.

## Where to Manage Tools

- Tools are managed in the Workspace tabs of OpenWebUI, where users can add models, prompts, and knowledge collections.

## Additional Notes

- Tools are designed to be pluggable, meaning you can easily import them into your system.
- Functions should be well-documented and follow OpenWebUI's guidelines for compatibility.
