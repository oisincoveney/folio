function makeFileKey(index, display) {
  if (crypto.randomUUID) return crypto.randomUUID()
  return `${Date.now()}-${index}-${display}`
}

function makePendingRow(name, key, sourceId) {
  return {
    file_key: key,
    source_id: sourceId,
    filename_original: name,
    amount: '', targetCurrency: 'EUR', paymentReference: '',
    company: '', invoiceNumber: '', invoiceDate: '', description: '', accountNumber: '',
    file_id: null, error: null, logs: [],
    status: 'pending', statusOk: false, savedAs: '', parsing: true,
  }
}

async function readAllDirectoryEntries(reader) {
  const entries = []
  while (true) {
    const batch = await new Promise(resolve => reader.readEntries(resolve))
    if (!batch.length) break
    entries.push(...batch)
  }
  return entries
}

async function entryToFiles(entry, path = '') {
  if (entry.isFile) {
    return new Promise(resolve => {
      entry.file(file => resolve([{ file, display: `${path}${file.name}` }]))
    })
  }

  if (!entry.isDirectory) return []

  const entries = await readAllDirectoryEntries(entry.createReader())
  const nested = await Promise.all(entries.map(child => entryToFiles(child, `${path}${entry.name}/`)))
  return nested.flat()
}

async function droppedItemsToFiles(items) {
  const entries = Array.from(items)
    .map(item => item.webkitGetAsEntry ? item.webkitGetAsEntry() : null)
    .filter(Boolean)

  if (!entries.length) return []

  const nested = await Promise.all(entries.map(entry => entryToFiles(entry)))
  return nested.flat()
}

document.addEventListener('alpine:init', () => {
  Alpine.data('filePicker', () => ({
    dragging: false,

    async handleDrop(e) {
      if (e.dataTransfer.items && e.dataTransfer.items.length) {
        const dropped = await droppedItemsToFiles(e.dataTransfer.items)
        if (dropped.length) {
          await this.startBatch(dropped)
          return
        }
      }
      await this.handleFiles(e.dataTransfer.files)
    },

    async handleFiles(files) {
      if (!files || files.length === 0) return
      const fileArr = Array.from(files).map(file => ({
        file,
        display: file.webkitRelativePath || file.name,
      }))
      await this.startBatch(fileArr)
    },

    async handleFileSelect(e) {
      await this.handleFiles(e.target.files)
      e.target.value = ''
    },

    async handleFolderSelect(e) {
      await this.handleFiles(e.target.files)
      e.target.value = ''
    },

    async startBatch(files) {
      const records = files
        .filter(({ file }) => file.name.toLowerCase().endsWith('.pdf'))
        .map(({ file, display }, index) => ({
          file,
          display: display || file.name,
          key: makeFileKey(index, display || file.name),
          sourceId: makeFileKey(index, `source-${display || file.name}`),
        }))

      if (!records.length) return

      const store = Alpine.store('app')
      store.reset()
      store.total = records.length
      store.parsing = true
      store.rows = records.map(record => makePendingRow(record.display, record.key, record.sourceId))
      store.selectedFileKey = store.rows[0]?.file_key || ''

      const fd = new FormData()
      records.forEach(record => {
        fd.append('files', record.file, record.display)
        fd.append('file_keys', record.key)
        fd.append('source_ids', record.sourceId)
      })
      fd.append('model', store.model)

      try {
        const parseRes = await fetch('/parse', { method: 'POST', body: fd })
        const parseBody = await parseRes.json()
        if (!parseRes.ok) throw new Error(parseBody.error || 'Unable to start parse')

        await store.streamJob(parseBody.job_id)
      } catch (e) {
        store.appendSystemLog(e.message)
        const active = store.rows.find(row => row.status === 'active') || store.rows.find(row => row.status === 'pending')
        if (active) {
          active.status = 'error'
          active.error = e.message
          active.parsing = false
        }
      }

      store.parsing = false
    },
  }))
})
