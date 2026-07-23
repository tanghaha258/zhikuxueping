<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Mathematics from '@tiptap/extension-mathematics'
import ImageExt from '@tiptap/extension-image'
import Table from '@tiptap/extension-table'
import TableRow from '@tiptap/extension-table-row'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import Underline from '@tiptap/extension-underline'
import 'katex/dist/katex.min.css'
import { uploadImageApi } from '@/api/upload'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const uploading = ref(false)

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit.configure({ history: { depth: 100 } }),
    Mathematics,
    ImageExt,
    Table.configure({ resizable: true }),
    TableRow,
    TableCell,
    TableHeader,
    Underline,
  ],
  editorProps: {
    attributes: { class: 'tiptap-editor' },
  },
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getHTML())
  },
})

watch(() => props.modelValue, (val) => {
  if (editor.value && editor.value.getHTML() !== val && val !== undefined) {
    editor.value.commands.setContent(val, false)
  }
})

onBeforeUnmount(() => editor.value?.destroy())

function insertImage() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    uploading.value = true
    try {
      const res = await uploadImageApi(file)
      const url = res.data?.data?.url
      if (url) {
        editor.value?.chain().focus().setImage({ src: url }).run()
      }
    } catch {
      ElMessage.error('图片上传失败')
    } finally {
      uploading.value = false
    }
  }
  input.click()
}

function insertMath() {
  const latex = window.prompt('请输入 LaTeX 公式：\n如: \\\\int_0^1 x^2 dx')
  if (latex) {
    editor.value?.chain().focus().insertContent(`$${latex}$`).run()
  }
}

function isActive(type: string, attrs?: Record<string, any>) {
  return editor.value?.isActive(type, attrs) ?? false
}
</script>

<template>
  <div class="tiptap-container">
    <div class="toolbar">
      <button type="button" class="toolbar-btn" :class="{ active: isActive('bold') }" @click="editor?.chain()?.focus()?.toggleBold()?.run()"><b>B</b></button>
      <button type="button" class="toolbar-btn" :class="{ active: isActive('italic') }" @click="editor?.chain()?.focus()?.toggleItalic()?.run()"><i>I</i></button>
      <button type="button" class="toolbar-btn" :class="{ active: isActive('underline') }" @click="editor?.chain()?.focus()?.toggleUnderline()?.run()"><u>U</u></button>
      <span class="divider" />
      <button type="button" class="toolbar-btn" :class="{ active: isActive('mathematics') }" @click="insertMath">Σ</button>
      <button type="button" class="toolbar-btn" :disabled="uploading" @click="insertImage">{{ uploading ? '上传中...' : '🖼' }}</button>
      <button type="button" class="toolbar-btn" :class="{ active: isActive('table') }" @click="editor?.chain()?.focus()?.insertTable?.({ rows: 3, cols: 3, withHeaderRow: true })?.run()">⊞</button>
      <span class="divider" />
      <button type="button" class="toolbar-btn" @click="editor?.chain()?.focus()?.clearNodes()?.unsetAllMarks()?.run()">清除</button>
    </div>
    <EditorContent :editor="editor" />
  </div>
</template>

<style scoped>
.tiptap-container { border: 1px solid #dcdfe6; border-radius: 4px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 2px; padding: 4px 8px; border-bottom: 1px solid #e4e7ed; background: #fafafa; }
.toolbar-btn { padding: 2px 8px; border: 1px solid transparent; border-radius: 3px; background: none; cursor: pointer; font-size: 13px; line-height: 1.8; color: #303133; }
.toolbar-btn:hover { background: #ecf5ff; border-color: #c6e2ff; }
.toolbar-btn.active { background: #409eff; color: #fff; }
.toolbar-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.divider { width: 1px; background: #dcdfe6; margin: 0 4px; flex-shrink: 0; }
:deep(.ProseMirror) { min-height: 60px; padding: 8px 12px; outline: none; }
:deep(.ProseMirror p) { margin: 4px 0; }
:deep(.ProseMirror img) { max-width: 100%; height: auto; border-radius: 4px; }
:deep(.ProseMirror table) { width: 100%; border-collapse: collapse; margin: 8px 0; }
:deep(.ProseMirror th), :deep(.ProseMirror td) { border: 1px solid #dcdfe6; padding: 4px 8px; text-align: left; }
:deep(.ProseMirror th) { background: #f5f7fa; font-weight: 600; }
</style>
