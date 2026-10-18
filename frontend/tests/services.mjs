export let ticketLoadError = new TypeError('Failed to fetch');
export function setTicketLoadError(value) { ticketLoadError = value; }
export async function fetchTickets() {
  if (ticketLoadError) throw ticketLoadError;
  return [];
}
export const fetchOrganizationTickets = fetchTickets;
export const createTicket = () => { throw new Error('Unexpected write'); };
export const createOrganizationTicket = createTicket;
export const deleteOrganizationTicket = createTicket;
export const deleteTicket = createTicket;
export const updateTicket = createTicket;
export const updateOrganizationTicket = createTicket;
export const updateTicketStatus = createTicket;
export const mapApiTicket = (ticket) => ticket;
let apiRequestHandler = () => { throw new Error('Unexpected API request'); };
export const setApiRequestHandler = (handler) => { apiRequestHandler = handler; };
export const apiRequest = (path, options) => apiRequestHandler(path, options);
const user = { id: 'test-user' };
let authState = { user, isLoading: false, configurationError: null };
export const setAuthState = (value) => { authState = value; };
export const useAuth = () => authState;
export const notificationSettingsFromUser = () => ({ newTickets: false, statusChanges: false });
export const getSupabaseClient = () => ({
  channel: () => ({ on() { return this; }, subscribe() { return this; } }),
  removeChannel() {},
});
