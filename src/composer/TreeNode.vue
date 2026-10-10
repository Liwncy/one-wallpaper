<script>
export default { name: "TreeNode" };
</script>

<script setup>
import { computed } from "vue";

const props = defineProps({
  value: { default: null },
  path: { type: String, default: "" },
  depth: { type: Number, default: 0 },
});
const emit = defineEmits(["pick"]);

const branch = computed(() => props.value !== null && typeof props.value === "object");
const entries = computed(() => {
  if (!branch.value) return [];
  if (Array.isArray(props.value)) return props.value.map((item, index) => [String(index), item]);
  return Object.entries(props.value);
});

function preview(value) {
  if (value === null) return "空";
  if (typeof value === "string") return value.length > 60 ? `${value.slice(0, 60)}…` : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `${value.length} 项`;
  if (typeof value === "object") return "对象";
  return String(value);
}

function childPath(key) {
  return props.path ? `${props.path}.${key}` : key;
}

function pick(event) {
  event.preventDefault();
  event.stopPropagation();
  emit("pick", props.path);
}
</script>

<template>
  <div v-if="!branch" class="node">
    <button type="button" class="pick-node" @click="pick">{{ path || "整段" }}</button>
    <span class="sample">{{ preview(value) }}</span>
  </div>
  <details v-else :open="depth < 1">
    <summary>
      <button type="button" class="pick-node" @click="pick">{{ path || "整段" }}</button>
      <span class="sample">{{ Array.isArray(value) ? `${value.length} 项` : "对象" }}</span>
    </summary>
    <TreeNode
      v-for="[key, child] in entries"
      :key="`${path}.${key}`"
      :value="child"
      :path="childPath(key)"
      :depth="depth + 1"
      @pick="emit('pick', $event)"
    />
  </details>
</template>
