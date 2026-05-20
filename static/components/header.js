document.addEventListener('alpine:init', () => {
  const preferredModel = 'anthropic/claude-opus-4-7'

  Alpine.data('header', () => ({
    open: false,
    query: '',
    loading: true,
    error: '',

    async init() {
      await this.loadModels()
    },

    async loadModels() {
      const store = Alpine.store('app')
      this.loading = true
      this.error = ''
      try {
        const res = await fetch('/models')
        if (!res.ok) throw new Error('Unable to load models')
        const models = await res.json()
        store.models = models.map(model => {
          if (typeof model === 'string') return { id: model, pdf: false }
          return { id: model.id, pdf: !!model.pdf }
        }).filter(model => model.id)

        if (!store.model && store.models.length) {
          const preferred = store.models.find(model => model.id === preferredModel)
          const firstPdf = store.models.find(model => model.pdf)
          store.model = (preferred || firstPdf || store.models[0]).id
        }
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },

    filteredModels() {
      const models = Alpine.store('app').models
      const q = this.query.trim().toLowerCase()
      if (!q) return models
      return models.filter(model => model.id.toLowerCase().includes(q))
    },

    filteredPdfModels() {
      return this.filteredModels().filter(model => model.pdf)
    },

    filteredNonPdfModels() {
      return this.filteredModels().filter(model => !model.pdf)
    },

    selectedLabel() {
      return Alpine.store('app').model || (this.loading ? 'Loading models...' : 'No model')
    },

    choose(model) {
      Alpine.store('app').model = model.id
      this.query = ''
      this.open = false
    },
  }))
})
