ADDON_NAME  = spherelinks_generator
ZIP         = $(ADDON_NAME).zip
BLENDER_DIR ?= $(HOME)/Library/Application Support/Blender/5.0/scripts/addons

.PHONY: build clean install-local test

build: clean
	@zip -r $(ZIP) $(ADDON_NAME) -x "*.pyc" "*__pycache__*" > /dev/null
	@ls -la $(ZIP)

clean:
	@rm -f $(ZIP)
	@find $(ADDON_NAME) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

install-local: build
	@rm -rf "$(BLENDER_DIR)/$(ADDON_NAME)"
	@unzip -q $(ZIP) -d "$(BLENDER_DIR)/"
	@echo "Installed into $(BLENDER_DIR)/$(ADDON_NAME)"
	@echo "⚠ Restart Blender (Cmd+Q / quit the whole process) to pick up the changes."

test:
	@for f in $(ADDON_NAME)/*.py; do \
		python3 -c "import ast; ast.parse(open('$$f').read())" && echo "  OK $$f" || echo "  FAIL $$f"; \
	done
