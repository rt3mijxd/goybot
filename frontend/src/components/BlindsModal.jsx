import React, { useState } from 'react'

export default function BlindsModal({ send, currentSb, currentBb }) {
  const [open, setOpen] = useState(false)
  const [sb, setSb] = useState(String(currentSb || 25))
  const [bb, setBb] = useState(String(currentBb || 50))

  const submit = () => {
    const sbVal = parseInt(sb) || 0
    const bbVal = parseInt(bb) || 0
    if (bbVal <= 0) return
    send({ action: 'set_blinds', sb: sbVal, bb: bbVal })
    setOpen(false)
  }

  if (!open) {
    return (
      <button
        onClick={() => {
          setSb(String(currentSb || 25))
          setBb(String(currentBb || 50))
          setOpen(true)
        }}
        className="bg-indigo-700 hover:bg-indigo-600 text-white px-4 py-2.5 rounded-lg transition text-sm"
      >
        {currentBb > 0 ? `Блайнды ${currentSb}/${currentBb}` : 'Ввести блайнды'}
      </button>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl p-3 flex items-center gap-2 flex-wrap">
      <span className="text-xs text-gray-400">SB:</span>
      <input
        type="number"
        value={sb}
        onChange={(e) => setSb(e.target.value)}
        className="w-16 bg-gray-700 rounded px-2 py-1 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
      <span className="text-xs text-gray-400">BB:</span>
      <input
        type="number"
        value={bb}
        onChange={(e) => setBb(e.target.value)}
        className="w-16 bg-gray-700 rounded px-2 py-1 text-white text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
      {[[10,20],[25,50],[50,100],[100,200]].map(([s,b]) => (
        <button key={b} onClick={() => { setSb(String(s)); setBb(String(b)) }}
          className="bg-gray-700 hover:bg-gray-600 text-xs px-2 py-1 rounded transition">
          {s}/{b}
        </button>
      ))}
      <button onClick={submit}
        className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-3 py-1 rounded-lg font-semibold transition">
        OK
      </button>
      <button onClick={() => setOpen(false)}
        className="text-gray-500 hover:text-gray-300 text-xs px-2 py-1 transition">
        ✕
      </button>
    </div>
  )
}
