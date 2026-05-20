import { useState, useEffect } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiGet } from '../../api/client.js'

export default function AdminPanel() {
  const { user } = useAuth()
  const [logs, setLogs] = useState([])
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('logs')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    loadLogs()
  }, [])

  async function loadLogs() {
    setLoading(true)
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
    setLoading(true)
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
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-slate-100 mb-6">
          Admin Panel — Audit Logs
        </h1>

        {/* Tabs */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-4 py-2 rounded ${
              activeTab === 'logs' ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            Query Logs
          </button>
          <button
            onClick={() => { setActiveTab('events'); loadEvents(); }}
            className={`px-4 py-2 rounded ${
              activeTab === 'events' ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            Guardrail Events
          </button>
        </div>

        {/* Date filters for events */}
        {activeTab === 'events' && (
          <div className="flex gap-4 mb-4">
            <input
              type="datetime-local"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100"
            />
            <input
              type="datetime-local"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100"
            />
            <button
              onClick={loadEvents}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
            >
              Filter
            </button>
          </div>
        )}

        {/* Log table */}
        {loading ? (
          <div className="text-slate-400">Loading...</div>
        ) : (
          <div className="bg-slate-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-700 text-left">
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Event</th>
                  <th className="p-3">User</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {(activeTab === 'logs' ? logs : events).map((entry, i) => (
                  <tr key={i} className="border-t border-slate-700">
                    <td className="p-3 text-slate-400">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-1 rounded text-xs ${
                        entry.event_type === 'guardrail_block' ? 'bg-red-900 text-red-300' :
                        entry.event_type === 'query' ? 'bg-blue-900 text-blue-300' :
                        'bg-slate-700 text-slate-300'
                      }`}>
                        {entry.event_type}
                      </span>
                    </td>
                    <td className="p-3 text-slate-300">{entry.user_id}</td>
                    <td className="p-3 text-slate-400">{entry.role}</td>
                    <td className="p-3 text-slate-400 max-w-xs truncate">
                      {JSON.stringify(entry.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
