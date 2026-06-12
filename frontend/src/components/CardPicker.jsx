import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
const SUITS = [
  { key: 's', symbol: '♠', color: 'text-gray-900' },
  { key: 'h', symbol: '♥', color: 'text-red-600' },
  { key: 'd', symbol: '♦', color: 'text-blue-500' },
  { key: 'c', symbol: '♣', color: 'text-green-700' },
]

export default function CardPicker({ onSelect, selectedCards = [], maxCards = 2, title = 'Выберите карты', autoConfirm = false }) {
  const [picked, setPicked] = useState([])

  const toggle = (card) => {
    if (selectedCards.includes(card)) return
    setPicked((prev) => {
      if (prev.includes(card)) {
        return prev.filter((c) => c !== card)
      }
      if (prev.length >= maxCards) return prev
      const next = [...prev, card]
      if (autoConfirm && next.length === maxCards) {
        setTimeout(() => {
          onSelect(next)
          setPicked([])
        }, 150)
      }
      return next
    })
  }

  const confirm = () => {
    if (picked.length > 0) {
      onSelect(picked)
      setPicked([])
    }
  }

  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-300">{title}</span>
        {!autoConfirm && picked.length > 0 && (
          <button
            onClick={confirm}
            className="bg-green-600 hover:bg-green-700 text-white text-xs font-semibold px-3 py-1 rounded-lg transition"
          >
            OK ({picked.length})
          </button>
        )}
        {autoConfirm && picked.length > 0 && picked.length < maxCards && (
          <span className="text-xs text-gray-400">{picked.length}/{maxCards}</span>
        )}
      </div>
      <div className="flex gap-1">
        {SUITS.map((suit) => (
          <div key={suit.key} className="flex flex-col gap-0.5">
            {RANKS.map((rank) => {
              const card = rank + suit.key
              const isSelected = picked.includes(card)
              const isUsed = selectedCards.includes(card)
              return (
                <button
                  key={card}
                  onClick={() => toggle(card)}
                  disabled={isUsed}
                  className={`w-11 h-9 rounded text-sm font-bold flex items-center justify-center gap-0.5 transition
                    ${isUsed
                      ? 'bg-gray-700 opacity-30 cursor-not-allowed'
                      : isSelected
                      ? 'bg-green-600 text-white ring-2 ring-green-400'
                      : 'bg-gray-600 hover:bg-gray-500 text-gray-200'
                    }`}
                >
                  <span>{rank}</span>
                  <span className={`text-xs ${suit.color}`}>{suit.symbol}</span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
