# Minimal Sphinx Makefile for AutomationMCP Superset documentation.
#
# Usage:
#   make html       — Build HTML docs (output: _build/html/index.html)
#   make latexpdf   — Build PDF via LaTeX (output: _build/latex/*.pdf)
#   make clean      — Remove all build artifacts
#   make help       — Show available targets

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html latexpdf clean


help:
	@echo "Available targets:"
	@echo "  html       Build HTML documentation"
	@echo "  latexpdf   Build PDF via LaTeX (requires texlive)"
	@echo "  clean      Remove build artifacts"

html:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

latexpdf:
	@echo "Building PDF (requires texlive-full or texlive-latex-extra)..."
	@$(SPHINXBUILD) -M latexpdf "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) 2>&1 || echo "PDF build failed — ensure texlive is installed: sudo apt install texlive-latex-extra"

clean:
	rm -rf "$(BUILDDIR)"
