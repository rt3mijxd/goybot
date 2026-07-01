import React, { createContext, useContext, useReducer, useMemo } from 'react'

const GameContext = createContext(null)

const initialState = {
  state: null,
  table_size: 0,
  positions: [],
  action_order: [],
  player_positions: [],
  opponent_positions: [],
  seats: {},
  pot: 0,
  sb: 0,
  bb: 0,
  board: [],
  current_turn: null,
  team_win_pct: 0,
  history: [],
  recommendation: null,
  recommendation_pos: null,
  opp_actions: {},
  is_responsible: false,
  responsible_name: '',
  members: {},
  seat_claimed: {},
  dealer_pos: null,
  sb_pos: null,
  bb_pos: null,
  position_labels: {},
  per_player_recs: {},
  my_recommendation: null,
  rec_action: null,
  spr: null,
  effective_stack: null,
  call_amount: 0,
  test_mode: false,
  street_complete: false,
  error: null,
}

function gameReducer(state, action) {
  switch (action.type) {
    case 'SET_STATE':
      return { ...state, ...action.payload, error: null }
    case 'SET_ERROR':
      return { ...state, error: action.payload }
    case 'CLEAR_ERROR':
      return { ...state, error: null }
    default:
      return state
  }
}

export function GameProvider({ children }) {
  const [state, dispatch] = useReducer(gameReducer, initialState)
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <GameContext.Provider value={value}>{children}</GameContext.Provider>
}

export function useGame() {
  return useContext(GameContext)
}
