/**
 * AuditLogViewer — C-Suite audit log panel.
 * 
 * Only renders if user role is c_suite (component-level enforcement).
 * Server-side enforcement in /audit/* endpoints is primary.
 */

import { useState, useEffect, useMemo } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiGet } from '../../api/client.js'

export default function AuditLogViewer() {
  const { user } = useAuth()
  const [logs, setLogs] = useState([])
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  // ── Component-level role check ───────────────────────────────────
  if (user?.role !== 'c_suite') {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-2">Access Denied</h1>
          <p className="text-slate-400">This page requires C-Suite Executive role.</p>
        </div>
      </div>
    )
  }

  // ── Fetch data on mount ──────────────────────────────────────────
  useEffect(() => {
    loadLogs()
    loadEvents()
  }, [])

  async function loadLogs() {
    try {
      const response = await apiGet('/audit/logs')
      if (response.ok) {
        const data = await response.json()
        setLogs(data.logs || [])
      }
    } catch (error) {
      console.error('Failed to load logs:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadEvents() {
    try {
      let url = '/audit/guardrail-events'
      const params = new URLSearchParams()
      if (startDate) params.set('start_date', startDate)
      if (endDate) params.set('end_date', endDate)
      if (params.toString()) url += '?' + params.toString()

      const response = await apiGet(url)
      if (response.ok) {
        const data = await response.json()
        setEvents(data.events || [])
      }
    } catch (error) {
      console.error('Failed to load events:', error)
    }
  }

  // ── Merge and filter logs ────────────────────────────────────────
  const filteredLogs = useMemo(() => {
    let items = activeTab === 'guardrail' ? events : [...logs, ...events]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      items = items.filter(item =>
        JSON.stringify(item).toLowerCase().includes(query)
      )
    }

    // Role filter
    if (roleFilter) {
      items = items.filter(item => item.role === roleFilter)
    }

    // Date range filter
    if (startDate) {
      const start = new Date(startDate)
      items = items.filter(item => new Date(item.timestamp) >= start)
    }
    if (endDate) {
      const end = new Date(endDate)
      items = items.filter(item => new Date(item.timestamp) <= end)
    }

    // Sort by timestamp descending
    return items.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
  }, [logs, events, activeTab, searchQuery, roleFilter, startDate, endDate])

  const roles = ['engineering', 'finance', 'marketing', 'hr', 'c_suite', 'employee']

  return (
    <div className="min-h-screen bg-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-100">Audit Logs</h1>
          <button
            onClick={() => { loadLogs(); loadEvents(); }}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm text-slate-300"
          >
            Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {[
            { id: 'all', label: 'All Logs' },
            { id: 'guardrail', label: 'Guardrail Events' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded text-sm ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-slate-800 rounded-lg p-4 mb-4 grid grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Search</label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search logs..."
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Role</label>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm"
            >
              <option value="">All Roles</option>
              {roles.map(role => (
                <option key={role} value={role}>{role}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Start Date</label>
            <input
              type="datetime-local"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">End Date</label>
            <input
              type="datetime-local"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm"
            />
          </div>
        </div>

        {/* Stats */}
        <div className="flex gap-4 mb-4 text-sm text-slate-400">
          <span>Total: {filteredLogs.length}</span>
          <span className="text-red-400">
            Guardrail triggers: {filteredLogs.filter(l => l.event_type?.includes('guardrail') || l.event_type?.includes('pii')).length}
          </span>
        </div>

        {/* Table */}
        {loading ? (
          <div className="text-center text-slate-400 py-8">Loading...</div>
        ) : (
          <div className="bg-slate-800 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-700 text-left text-slate-300">
                    <th className="p-3">Timestamp</th>
                    <th className="p-3">Event</th>
                    <th className="p-3">User</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Query / Details</th>
                    <th className="p-3">Guardrail</th>
                    <th className="p-3">Block Reason</th>
                    <th className="p-3">RAGAS</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.map((entry, i) => {
                    const isGuardrail = entry.event_type?.includes('guardrail') || entry.event_type?.includes('pii')
                    const details = entry.details || {}

                    return (
                      <tr
                        key={i}
                        className={`border-t border-slate-700 ${
                          isGuardrail ? 'bg-red-900/20' : ''
                        }`}
                      >
                        <td className="p-3 text-slate-400 whitespace-nowrap">
                          {formatTimestamp(entry.timestamp)}
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs ${getEventBadgeClass(entry.event_type)}`}>
                            {entry.event_type}
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">
                          {entry.user_id || '—'}
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs ${getRoleBadgeClass(entry.role)}`}>
                            {entry.role}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400 max-w-xs truncate">
                          {details.query_preview || JSON.stringify(details).slice(0, 50)}
                        </td>
                        <td className="p-3">
                          {isGuardrail ? (
                            <span className="text-red-400 font-medium">✓</span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                        <td className="p-3 text-slate-400">
                          {details.block_reason || details.reason || '—'}
                        </td>
                        <td className="p-3 text-slate-400">
                          {details.scores ? (
                            <span className="text-xs">
                              {Object.entries(details.scores)
                                .filter(([_, v]) => v != null)
                                .map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`)
                                .join(', ')}
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {filteredLogs.length === 0 && (
              <div className="text-center text-slate-500 py-8">
                No logs found matching filters
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function formatTimestamp(ts) {
  if (!ts) return '—'
  const date = new Date(ts)
  return date.toLocaleString()
}

function getEventBadgeClass(eventType) {
  if (eventType?.includes('guardrail') || eventType?.includes('pii')) {
    return 'bg-red-900 text-red-300'
  }
  if (eventType === 'query') return 'bg-blue-900 text-blue-300'
  if (eventType === 'ragas_evaluation') return 'bg-green-900 text-green-300'
  return 'bg-slate-700 text-slate-300'
}

function getRoleBadgeClass(role) {
  const classes = {
    engineering: 'bg-violet-900 text-violet-300',
    finance: 'bg-emerald-900 text-emerald-300',
    marketing: 'bg-orange-900 text-orange-300',
    hr: 'bg-rose-900 text-rose-300',
    c_suite: 'bg-amber-900 text-amber-300',
    employee: 'bg-slate-700 text-slate-300',
  }
  return classes[role] || 'bg-slate-700 text-slate-300'
}
