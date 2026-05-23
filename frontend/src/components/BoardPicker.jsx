import React, { useState } from 'react'
import { useGame } from '../context/GameContext'
import CardPicker from './CardPicker'

export default function BoardPicker({ send }) {
  const { state } = useGame()
  const gs = state.state
  const board = state.board || []

  const allUsedCards = []
  for (const seat of Object.values(state.seats || {})) {
    if (seat?.player?.cards) {
      for (const c of seat.player.cards) {
        if (c !== '??') allUsedCards.push(c)
      }
    }
  }
  for (const c of board) allUsedCards.push(c)

  let maxCards = 3
  let title = 'Флоп (3 карты)'
  if (gs === 'PREFLOP' || gs === 'DEALING') {
    maxCards = 3
    title = 'Флоп (3 карты)'
  } else if (gs === 'FLOP') {
    maxCards = 1
    title = 'Тёрн (1 карта)'
  } else if (gs === 'TURN') {
    maxCards = 1
    title = 'Ривер (1 карта)'
  } else {
    return null
  }

  const handleSelect = (cards) => {
    send({ action: 'board', cards })
  }

  return (
    <div className="flex-1 min-w-[300px]">
      <CardPicker
        onSelect={handleSelect}
        selectedCards={allUsedCards}
        maxCards={maxCards}
        title={title}
      />
    </div>
  )
}
