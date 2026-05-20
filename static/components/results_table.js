document.addEventListener('alpine:init', () => {
  Alpine.data('resultsTable', () => ({
    destDir: '',
    saveResult: '',

    async pickDestDir() {
      const res = await fetch('/pick-folder')
      const { path } = await res.json()
      if (path) this.destDir = path
    },

    async saveAll() {
      if (!this.destDir) {
        await this.pickDestDir()
        if (!this.destDir) return
      }
      const store = Alpine.store('app')
      store.saving = true
      this.saveResult = ''
      try {
        const res = await fetch('/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dest_dir: this.destDir,
            rows: store.rows
              .filter(r => !r.parsing && r.file_id)
              .map(({
                file_key, source_id, filename_original, amount, targetCurrency,
                paymentReference, company, invoiceNumber, invoiceDate, description,
                accountNumber, file_id,
              }) => ({
                file_key, source_id, filename_original, amount, targetCurrency,
                paymentReference, company, invoiceNumber, invoiceDate, description,
                accountNumber, file_id,
              })),
          }),
        })
        const results = await res.json()
        let saved = 0
        results.forEach(r => {
          const row = store.rows.find(x => x.file_key === r.file_key)
            || store.rows.find(x => x.filename_original === r.filename_original)
          if (row) {
            row.savedAs = r.success ? `✓ ${r.filename}` : `Error: ${r.error}`
            row.statusOk = r.success
            if (r.success) saved++
          }
        })
        this.saveResult = `${saved} of ${results.length} saved`
      } catch (e) {
        this.saveResult = `Error: ${e.message}`
      }
      store.saving = false
    },
  }))
})
