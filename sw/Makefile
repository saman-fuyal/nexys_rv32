# =============================================================================
# sw/Makefile - convenience wrapper around sw/build.py (Linux, WSL, or Windows
# with make on PATH). build.py does the work so Windows needs no make.
#   make            build everything (boot ROM + all programs)
#   make hello      one program        make clean   remove sw/build
#   make COMPILER=clang   clang/lld cross-check build
# =============================================================================
PY  ?= python3
COMPILER ?= gcc
TARGETS := boot hello switches_leds seg7_counter timer_irq dhrystone coremark

all:
	$(PY) build.py --cc $(COMPILER)

$(TARGETS):
	$(PY) build.py $@ --cc $(COMPILER)

clean:
	$(PY) -c "import shutil; shutil.rmtree('build', True)"

.PHONY: all clean $(TARGETS)
