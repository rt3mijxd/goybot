import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import CardPicker from './CardPicker'
import Card from './Card'

export default function BoardPicker({ send }) {
  const { state } = useGame()
  const [editing, setEditing] = useState(false)
  const gs = state.state
  const board = state.board || []

  // Карты игроков — всегда заблокированы в пикере
  const playerCards = []
  for (const seat of Object.values(state.seats || {})) {
    if (seat?.player?.cards) {
      for (const c of seat.player.cards) {
        if (c !== '??') playerCards.push(c)
      }
    }
  }

  // Сколько карт нужно выбрать для текущей улицы
  let maxCards = 3
  let title = 'Флоп (3 карты)'
  if (gs === 'PREFLOP' || gs === 'DEALING') {
    maxCards = 3; title = 'Флоп (3 карты)'
  } else if (gs === 'FLOP') {
    maxCards = 1; title = 'Тёрн (1 карта)'
  } else if (gs === 'TURN') {
    maxCards = 1; title = 'Ривер (1 карта)'
  } else {
    return null
  }

  // Если уже есть карты на борде и не режим редактирования —
  // показываем борд + кнопку редактирования
  if (board.length > 0 && !editing) {
    return (
      <div className="bg-gray-800 rounded-xl p-3 flex items-center gap-3 flex-wrap">
        <span className="text-xs text-gray-400 font-semibold">Борд:</span>
        <div className="flex gap-1">
          {board.map((c, i) => <Card key={i} card={c} size="sm" />)}
        </div>
        <button
          onClick={() => setEditing(true)}
          className="ml-auto text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-1.5 rounded-lg transition"
        >
          ✎ Изменить борд
        </button>
      </div>
    )
  }

  // Режим редактирования: разрешаем выбрать заново весь борд текущей улицы
  // При редактировании карты борда НЕ блокируются (можно переиспользовать)
  const handleSelect = (cards) => {
    send({ action: 'board', cards })
    setEditing(false)
  }

  return (
    <div className="flex-1 min-w-[300px]">
      {editing && (
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-yellow-400 font-semibold">Замена борда</span>
          <button
            onClick={() => setEditing(false)}
            className="text-xs text-gray-500 hover:text-gray-300 ml-auto transition"
          >
            Отмена
          </button>
        </div>
      )}
      <CardPicker
        onSelect={handleSelect}
        selectedCards={playerCards}
        maxCards={maxCards}
        title={title}
        autoConfirm={true}
      />
    </div>
  )
}
