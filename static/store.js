document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    model: '',
    models: [],
    rows: [],
    selectedFileKey: '',
    parsing: false,
    saving: false,
    completed: 0,
    total: 0,
    retryQueue: [],
    retryRunning: false,

    selectedRow() {
      return this.rows.find(r => r.file_key === this.selectedFileKey) || this.rows[0] || null
    },

    selectRow(row) {
      if (row) this.selectedFileKey = row.file_key
    },

    rowForEvent(ev) {
      return this.rows.find(r => r.file_key && r.file_key === ev.file_key)
        || this.rows.find(r => r.filename_original === (ev.filename || ev.filename_original))
    },

    statusCounts() {
      return {
        active: this.rows.filter(r => r.status === 'active').length,
        done: this.rows.filter(r => r.status === 'done').length,
        error: this.rows.filter(r => r.status === 'error').length,
        pending: this.rows.filter(r => r.status === 'pending').length,
      }
    },

    isQueued(row) {
      return !!row && this.retryQueue.includes(row.file_key)
    },

    stripAnsi(text) {
      return (text || '').replace(/\x1b\[[0-9;]*m/g, '')
    },

    readableValue(value) {
      if (value === null || value === undefined || value === '') return ''
      if (typeof value === 'string') return value
      if (typeof value === 'number' || typeof value === 'boolean') return String(value)
      return JSON.stringify(value, null, 2)
    },

    readableObject(obj, skip = []) {
      return Object.entries(obj || {})
        .filter(([key, value]) => !skip.includes(key) && value !== null && value !== undefined && value !== '')
        .map(([key, value]) => {
          const readable = this.readableValue(value)
          return readable.includes('\n') ? `${key}:\n${readable}` : `${key}: ${readable}`
        })
        .join('\n')
    },

    eventContent(parsed) {
      const part = parsed.part
      if (part && typeof part.text === 'string') return part.text
      if (typeof parsed.text === 'string') return parsed.text
      if (part && typeof part.content === 'string') return part.content
      if (typeof parsed.content === 'string') return parsed.content
      if (part && typeof part.reasoning === 'string') return part.reasoning
      if (typeof parsed.reasoning === 'string') return parsed.reasoning
      if (part && typeof part.thought === 'string') return part.thought
      if (typeof parsed.thought === 'string') return parsed.thought
      return ''
    },

    renderToolUse(part) {
      const tool = part.tool || part.name || part.id || 'tool'
      const lines = []
      if (part.description) lines.push(part.description)
      if (part.input) lines.push(`Input:\n${this.readableValue(part.input)}`)
      if (part.state?.input) lines.push(`Input:\n${this.readableValue(part.state.input)}`)
      if (part.output) lines.push(`Output:\n${this.readableValue(part.output)}`)
      if (part.state?.output) lines.push(`Output:\n${this.readableValue(part.state.output)}`)
      if (part.error) lines.push(`Error: ${part.error}`)
      if (part.state?.error) lines.push(`Error: ${part.state.error}`)
      if (!lines.length) {
        lines.push(this.readableObject(part, ['id', 'sessionID', 'messageID']))
      }
      return { meta: tool, body: lines.filter(Boolean).join('\n\n') }
    },

    renderStepFinish(parsed) {
      const lines = []
      if (parsed.reason) lines.push(`Reason: ${parsed.reason}`)
      if (parsed.cost !== undefined) lines.push(`Cost: $${Number(parsed.cost).toFixed(4)}`)
      if (parsed.tokens) {
        const tokens = parsed.tokens
        lines.push(`Tokens: ${tokens.total || 0} total, ${tokens.input || 0} in, ${tokens.output || 0} out`)
      }
      if (parsed.time?.start && parsed.time?.end) {
        lines.push(`Duration: ${Math.max(0, parsed.time.end - parsed.time.start)}ms`)
      }
      return lines.join('\n')
    },

    parseOpenCodeLine(ev) {
      const entry = {
        stream: ev.stream || 'stdout',
        raw: ev.text || '',
        expanded: false,
        technical: false,
        json: null,
        type: 'raw',
        title: ev.stream || 'stdout',
        body: this.stripAnsi(ev.text || ''),
        meta: '',
      }

      try {
        const parsed = JSON.parse(entry.raw)
        entry.json = parsed
        entry.type = parsed.type || 'json'
        entry.title = entry.type
        entry.meta = parsed.part?.type || parsed.part?.tool || parsed.reason || ''
        entry.technical = ['step_start', 'step_finish'].includes(entry.type)

        const emittedContent = this.eventContent(parsed)

        if (entry.type === 'step_start') {
          entry.body = parsed.messageID ? `messageID: ${parsed.messageID}` : 'step started'
          entry.meta = parsed.id || ''
        } else if (entry.type === 'step_finish') {
          entry.body = this.renderStepFinish(parsed) || 'step finished'
          entry.meta = parsed.reason || ''
        } else if (entry.type === 'tool_use') {
          const tool = this.renderToolUse(parsed.part || parsed)
          entry.body = tool.body
          entry.meta = tool.meta
        } else if (emittedContent) {
          entry.body = emittedContent
        } else if (parsed.part && typeof parsed.part === 'object') {
          entry.body = this.readableObject(parsed.part, ['id', 'sessionID', 'messageID'])
            || this.readableObject(parsed, ['id', 'sessionID', 'messageID', 'snapshot'])
        } else {
          entry.body = this.readableObject(parsed, ['id', 'sessionID', 'messageID', 'snapshot'])
            || entry.raw
        }
      } catch (_) {
        entry.type = entry.stream === 'stderr' ? 'stderr' : 'raw'
        entry.title = entry.type
      }

      return entry
    },

    appendSystemLog(text, row = null) {
      const target = row || this.selectedRow() || this.rows.find(r => r.status === 'active')
      if (!target) return
      target.logs.push({
        stream: 'system',
        raw: text,
        expanded: false,
        technical: false,
        json: null,
        type: 'system',
        title: 'system',
        body: text,
        meta: '',
      })
    },

    async streamJob(jobId) {
      await new Promise((resolve, reject) => {
        const es = new EventSource(`/stream/${jobId}`)
        es.onmessage = e => {
          const ev = JSON.parse(e.data)
          if (ev.type === 'done') {
            es.close()
            resolve()
          } else {
            this.handleEvent(ev)
          }
        }
        es.onerror = () => {
          this.appendSystemLog('Stream disconnected')
          es.close()
          reject(new Error('Stream disconnected'))
        }
      })
    },

    async runRetryQueue() {
      if (this.retryRunning || !this.retryQueue.length) return
      const retryable = this.retryQueue
        .map(fileKey => this.rows.find(row => row.file_key === fileKey))
        .filter(row => row?.source_id && row.status === 'pending')

      this.retryQueue = this.retryQueue.filter(
        fileKey => !retryable.some(row => row.file_key === fileKey),
      )
      if (!retryable.length) return

      this.retryRunning = true
      this.parsing = true
      retryable.forEach(row => {
        row.parsing = true
        this.appendSystemLog('Retry started', row)
      })

      try {
        const res = await fetch('/retry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: this.model,
            rows: retryable.map(({ file_key, source_id, filename_original }) => ({
              file_key,
              source_id,
              filename_original,
            })),
          }),
        })
        const body = await res.json()
        if (!res.ok) throw new Error(body.error || 'Unable to retry')
        await this.streamJob(body.job_id)
      } catch (e) {
        retryable.forEach(row => {
          if (row.parsing) {
            row.status = 'error'
            row.error = e.message
            row.parsing = false
            this.completed++
            this.appendSystemLog(e.message, row)
          }
        })
      }
      this.retryRunning = false
      this.parsing = false
      if (this.retryQueue.length) await this.runRetryQueue()
    },

    retryRows(rows) {
      const retryable = rows.filter(row => row?.source_id && row.status === 'error')
      if (!retryable.length) return

      retryable.forEach(row => {
        if (!this.retryQueue.includes(row.file_key)) {
          this.retryQueue.push(row.file_key)
        }
        row.status = 'pending'
        row.parsing = false
        row.error = null
        row.file_id = null
        row.savedAs = ''
        row.statusOk = false
        this.appendSystemLog('Retry queued', row)
      })
      this.completed = Math.max(0, this.completed - retryable.length)
      if (!this.parsing) return this.runRetryQueue()
    },

    retryFailed() {
      return this.retryRows(this.rows)
    },

    retryRow(row) {
      return this.retryRows(row ? [row] : [])
    },

    handleEvent(ev) {
      const row = this.rowForEvent(ev)
      if (ev.type === 'start') {
        if (row) {
          row.status = 'active'
          row.parsing = true
          if (ev.source_id) row.source_id = ev.source_id
          if (!this.selectedFileKey) this.selectedFileKey = row.file_key
        }
      } else if (ev.type === 'batch_start') {
        this.appendSystemLog(`Running up to ${ev.parallelism} files in parallel`)
      } else if (ev.type === 'raw_log') {
        if (row) row.logs.push(this.parseOpenCodeLine(ev))
      } else if (ev.type === 'attempt') {
        if (row) {
          row.status = 'active'
          row.parsing = true
          this.appendSystemLog(`Attempt ${ev.attempt} of ${ev.max_attempts}`, row)
        }
      } else if (ev.type === 'retrying') {
        if (row) {
          this.appendSystemLog(
            `Retrying after attempt ${ev.attempt - 1}: ${ev.error}`,
            row,
          )
        }
      } else if (ev.type === 'result') {
        if (row) {
          row.amount = ev.amount
          row.targetCurrency = ev.targetCurrency || 'EUR'
          row.company = ev.company || ''
          row.invoiceNumber = ev.invoiceNumber || ''
          row.invoiceDate = ev.invoiceDate || ''
          row.description = ev.description || ''
          row.accountNumber = ev.accountNumber || ''
          row.paymentReference = ev.paymentReference
          row.file_id = ev.file_id
          row.error = ev.error
          if (ev.source_id) row.source_id = ev.source_id
          row.status = ev.error ? 'error' : 'done'
          row.parsing = false
        }
        this.completed++
        if (this.parsing && this.completed >= this.total && this.retryQueue.length) {
          this.runRetryQueue()
        }
      } else if (ev.type === 'error') {
        const active = this.rows.find(r => r.status === 'active') || this.selectedRow()
        if (active) {
          active.status = 'error'
          active.error = ev.error || 'Stream error'
          active.parsing = false
          active.logs.push({
            stream: 'system',
            raw: active.error,
            expanded: true,
            json: null,
            type: 'system',
            title: 'system',
            body: active.error,
          })
        }
      }
    },

    reset() {
      this.rows = []
      this.selectedFileKey = ''
      this.parsing = false
      this.saving = false
      this.completed = 0
      this.total = 0
      this.retryQueue = []
      this.retryRunning = false
    },
  })
})
