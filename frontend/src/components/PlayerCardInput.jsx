import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import CardPicker from './CardPicker'

export default function PlayerCardInput({ send, userId }) {
  const { state } = useGame()
  const [showPicker, setShowPicker] = useState(false)

  // Найти позицию текущего игрока
  const myEntry = Object.entries(state.seats || {}).find(
    ([, s]) => s?.type === 'our' && s.player?.user_id === userId
  )
  if (!myEntry) return null

  const [myPos, mySeat] = myEntry
  const myCards = mySeat.player?.cards || []
  const hasCards = myCards.length === 2 && !myCards.includes('??')

  // Карты других — уже занятые
  const usedCards = []
  for (const [, s] of Object.entries(state.seats || {})) {
    if (s?.player?.cards) {
      for (const c of s.player.cards) {
        if (c !== '??' ) usedCards.push(c)
      }
    }
  }
  for (const c of (state.board || [])) usedCards.push(c)

  const myLabel = state.position_labels?.[myPos] || myPos

  if (hasCards) {
    return (
      <div className="bg-green-900/50 border border-green-600/50 rounded-xl p-3 mx-2">
        <div className="text-sm text-green-300 text-center">
          Ваши карты ({myLabel}): <span className="font-bold">{myCards.join(' ')}</span>
        </div>
      </div>
    )
  }

  const handleSelect = (cards) => {
    send({ action: 'set_my_cards', cards })
    setShowPicker(false)
  }

  return (
    <div className="bg-gray-800 rounded-xl p-3 mx-2">
      <h3 className="text-sm font-bold mb-2 text-center">Введите свои карты ({myLabel})</h3>
      {!showPicker ? (
        <button
          onClick={() => setShowPicker(true)}
          className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2.5 rounded-lg transition text-sm"
        >
          Выбрать карты
        </button>
      ) : (
        <CardPicker
          onSelect={handleSelect}
          selectedCards={usedCards}
          maxCards={2}
          title="Ваши карты"
        />
      )}
    </div>
  )
}
