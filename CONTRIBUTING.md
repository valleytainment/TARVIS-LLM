# Contributing to TARVIS-LLM

Thank you for your interest in contributing to TARVIS-LLM!

## How to Contribute

We welcome contributions in various forms, including:

*   **Bug Reports:** If you find a bug, please open an issue on GitHub detailing the problem, steps to reproduce, and your environment.
*   **Feature Requests:** Have an idea for a new skill or improvement? Open an issue to discuss it.
*   **Code Contributions:** 
    *   Fork the repository.
    *   Create a new branch for your feature or bug fix.
    *   Make your changes, adhering to the existing code style.
    *   Add unit tests for any new functionality.
    *   Ensure all tests pass.
    *   Submit a pull request against the `main` branch.
*   **Documentation:** Improvements to the README or other documentation are always welcome.

## Development Setup

1.  Clone the repository.
2.  Set up a Python virtual environment (e.g., using `venv` or `conda`).
3.  Install dependencies: `pip install -r requirements.txt`
4.  Set up your `.env` file based on `.env.example` (if provided) or the README instructions, including paths to your LLM model.
5.  Run the application: `python -m src.gui.main_window`

## Code Style

Please try to follow the existing code style (PEP 8 for Python). Use clear variable names and add comments where necessary.

## Testing

Run unit tests using:
```bash
python -m unittest discover tests
```
Ensure all tests pass before submitting a pull request.

Thank you for contributing!

