import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import CardPicker from './CardPicker'

export default function DealCards({ send }) {
  const { state } = useGame()
  const [dealtCards, setDealtCards] = useState({})
  const [activePos, setActivePos] = useState(null)

  const playerPositions = state.player_positions || []

  const allUsed = Object.values(dealtCards).flat()

  const handleSelect = (cards) => {
    if (!activePos) return
    setDealtCards((prev) => ({ ...prev, [activePos]: cards }))
    setActivePos(null)
  }

  const submitDeal = () => {
    const hasCards = Object.values(dealtCards).some((c) => c.length > 0)
    if (!hasCards) return
    send({ action: 'deal_cards', cards: dealtCards })
  }

  const allDealt = playerPositions.every((pos) => (dealtCards[pos] || []).length === 2)

  return (
    <div className="bg-gray-800 rounded-xl p-4 mx-2 mt-2">
      <h3 className="text-lg font-bold mb-3">Раздайте карты</h3>
      <div className="flex gap-3 flex-wrap mb-3">
        {playerPositions.map((pos) => {
          const cards = dealtCards[pos] || []
          const seat = state.seats?.[pos]
          const name = seat?.player?.name || `Д${seat?.player?.number || '?'}`
          return (
            <button
              key={pos}
              onClick={() => setActivePos(pos)}
              className={`px-4 py-3 rounded-xl text-sm font-semibold transition ${
                activePos === pos
                  ? 'bg-green-600 ring-2 ring-green-400'
                  : cards.length === 2
                  ? 'bg-green-800 text-green-200'
                  : 'bg-gray-700 hover:bg-gray-600'
              }`}
            >
              <div>{name} ({pos})</div>
              <div className="text-xs mt-1">
                {cards.length === 2 ? cards.join(' ') : 'нет карт'}
              </div>
            </button>
          )
        })}
      </div>

      {activePos && (
        <CardPicker
          onSelect={handleSelect}
          selectedCards={allUsed}
          maxCards={2}
          title={`Карты для ${activePos}`}
        />
      )}

      <button
        onClick={submitDeal}
        disabled={!allDealt}
        className="w-full mt-3 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-semibold py-3 rounded-lg transition"
      >
        Раздать карты
      </button>
    </div>
  )
}
