# --- Configuration ---
APP_NAME = "MiniProcessor"
ENTRY_POINT = main_gui.py
DIST_DIR = dist
BUILD_DIR = build
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# --- Build Targets ---

.PHONY: all
all: install build clean_temp

.PHONY: venv
venv:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

.PHONY: install
install: venv
	@echo "Installing dependencies..."
	$(PIP) install opencv-python Pillow reportlab tkinterdnd2 pyinstaller

.PHONY: build
build:
	@echo "Building macOS Application..."
	$(PYTHON) -m PyInstaller --noconsole --onefile --windowed \
		--collect-all tkinterdnd2 \
		--name $(APP_NAME) \
		$(ENTRY_POINT)
	@echo "Build complete! Check the /$(DIST_DIR) folder."

.PHONY: clean
clean:
	@echo "Cleaning up build artifacts..."
	rm -rf $(BUILD_DIR) $(DIST_DIR) *.spec

.PHONY: clean_temp
clean_temp:
	@echo "Cleaning temporary build files..."
	rm -rf $(BUILD_DIR) *.spec

.PHONY: run
run:
	@echo "Running application..."
	$(PYTHON) $(ENTRY_POINT)
