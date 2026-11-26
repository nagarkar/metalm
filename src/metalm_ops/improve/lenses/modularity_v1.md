---
id: modularity_v1
version: 1
may_change_behaviour: false
needs_measurement: false
max_files: 6
max_changed_lines: 300
---
Improve the structure the finding measures, with no behaviour change: separation of concerns, encapsulation and modularity. Typical fixes: extract a cohesive helper or small class from an oversized or overly complex function; split a function that does several jobs into named steps; move a group of related functions out of an oversized module into a new module and import them back; replace reaching into another module's private names (`other._thing`) with a public function or method on the owner; turn module-level mutable state changed through `global` into an object or explicit parameter; group a long parameter list into a small dataclass when the same group travels together; break an import cycle by moving the shared piece to a lower module. Keep every public name and its behaviour (re-export moved names from their old module), keep the change reviewable in one sitting, and prefer the smallest structural step that measurably improves the finding over a broad rewrite. Quote the structure you change as evidence.
