document.addEventListener('alpine:init', () => {
  Alpine.data('fileInspector', () => ({
    showTechnical: false,

    init() {
      this.$watch(() => Alpine.store('app').selectedFileKey, () => {
        this.$nextTick(() => this.scrollLogs())
      })
      this.$watch(() => Alpine.store('app').selectedRow()?.logs.length, () => {
        this.$nextTick(() => this.scrollLogs())
      })
    },

    row() {
      return Alpine.store('app').selectedRow()
    },

    visibleLogs() {
      const row = this.row()
      if (!row) return []
      if (this.showTechnical) return row.logs
      return row.logs.filter(entry => !entry.technical)
    },

    hiddenTechnicalCount() {
      const row = this.row()
      if (!row || this.showTechnical) return 0
      return row.logs.filter(entry => entry.technical).length
    },

    retrySelected() {
      return Alpine.store('app').retryRow(this.row())
    },

    isQueued() {
      return Alpine.store('app').isQueued(this.row())
    },

    cleanReferencePart(value) {
      return String(value || '').trim()
    },

    rebuildReference() {
      const row = this.row()
      if (!row) return
      const company = this.cleanReferencePart(row.company)
      const invoice = this.cleanReferencePart(row.invoiceNumber)
      const description = this.cleanReferencePart(row.description)
      const account = this.cleanReferencePart(row.accountNumber)
      const parts = [company]
      if (invoice) parts.push(`Inv ${invoice}`)
      else if (account) parts.push(account)
      if (description && description.toLowerCase() !== company.toLowerCase()) {
        parts.push(description)
      }
      row.paymentReference = parts
        .filter(Boolean)
        .filter((part, index, arr) => arr.findIndex(x => x.toLowerCase() === part.toLowerCase()) === index)
        .join(' - ')
        .slice(0, 80)
    },

    scrollLogs() {
      const el = this.$refs.logPanel
      if (el) el.scrollTop = el.scrollHeight
    },

    async copyRaw(entry) {
      if (navigator.clipboard) await navigator.clipboard.writeText(entry.raw)
    },
  }))
})
