import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import CardPicker from './CardPicker'
import Card from './Card'

export default function BoardPicker({ send }) {
  const { state } = useGame()
  const [editing, setEditing] = useState(false)
  const gs = state.state
  const board = state.board || []

  // Карты игроков — заблокированы в пикере
  const playerCards = []
  for (const seat of Object.values(state.seats || {})) {
    if (seat?.player?.cards) {
      for (const c of seat.player.cards) {
        if (c !== '??') playerCards.push(c)
      }
    }
  }

  // Настройки пикера для НОВОЙ улицы
  let newCardCount = 3
  let newTitle = 'Флоп (3 карты)'
  if (gs === 'PREFLOP' || gs === 'DEALING') {
    newCardCount = 3; newTitle = 'Флоп (3 карты)'
  } else if (gs === 'FLOP') {
    newCardCount = 1; newTitle = 'Тёрн (1 карта)'
  } else if (gs === 'TURN') {
    newCardCount = 1; newTitle = 'Ривер (1 карта)'
  } else {
    return null
  }

  // Режим редактирования — замена СУЩЕСТВУЮЩИХ карт борда
  if (editing) {
    return (
      <div className="flex-1 min-w-[300px]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-yellow-400 font-semibold">
            Замена борда ({board.length} карт)
          </span>
          <button
            onClick={() => setEditing(false)}
            className="text-xs text-gray-500 hover:text-gray-300 ml-auto transition"
          >
            Отмена
          </button>
        </div>
        <CardPicker
          onSelect={(cards) => { send({ action: 'board_replace', cards }); setEditing(false) }}
          selectedCards={playerCards}
          maxCards={board.length}
          title={`Новые карты борда (${board.length})`}
          autoConfirm={board.length === 1}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 flex-1 min-w-[300px]">
      {/* Существующие карты борда с кнопкой редактирования */}
      {board.length > 0 && (
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
      )}

      {/* Пикер для карт НОВОЙ улицы — борд блокирует уже использованные карты */}
      <CardPicker
        onSelect={(cards) => send({ action: 'board', cards })}
        selectedCards={[...playerCards, ...board]}
        maxCards={newCardCount}
        title={newTitle}
        autoConfirm={true}
      />
    </div>
  )
}
