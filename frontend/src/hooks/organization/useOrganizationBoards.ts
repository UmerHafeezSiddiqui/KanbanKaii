import { useEffect, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from 'react';
import { toast } from 'sonner';
import {
  addOrganizationBoardMember,
  addOrganizationBoardSlackChannel,
  changeOrganizationBoardMemberRole,
  createOrganizationBoard,
  deleteOrganizationBoard,
  listOrganizationBoardMembers,
  listOrganizationBoardSlackChannels,
  listOrganizationBoards,
  removeOrganizationBoardMember,
  removeOrganizationBoardSlackChannel,
  type Organization,
  type OrganizationBoard,
  type OrganizationBoardMember,
  type OrganizationBoardRole,
  type OrganizationBoardSlackChannel,
} from '@/api/organizations';
import { slugify } from '@/components/organization/organization-ui';
import {
  refreshOrganizationSlackChannels,
  type OrganizationSlackBindingStatus,
  type SlackChannelRefreshResponse,
} from '@/integrations/slack/api';

type OrganizationBoardsOptions = {
  canCreateBoards: boolean;
  organization: Organization | null;
  selectedBoard: OrganizationBoard | null;
  setBoardMembers: Dispatch<SetStateAction<OrganizationBoardMember[]>>;
  setBoards: (boards: OrganizationBoard[]) => void;
  setBoardSlackChannels: Dispatch<SetStateAction<OrganizationBoardSlackChannel[]>>;
  setConfirmBoardDelete: (boardId: string | null) => void;
  setConfirmBoardMemberRemove: (userId: string | null) => void;
  setConfirmSlackChannelRemove: (channelId: string | null) => void;
  setIsSaving: (isSaving: boolean) => void;
  setSelectedBoardId: (boardId: string | null) => void;
  setShowSlackChannelForm: (show: boolean) => void;
  slackBinding: OrganizationSlackBindingStatus;
};

export function useOrganizationBoards({
  canCreateBoards,
  organization,
  selectedBoard,
  setBoardMembers,
  setBoards,
  setBoardSlackChannels,
  setConfirmBoardDelete,
  setConfirmBoardMemberRemove,
  setConfirmSlackChannelRemove,
  setIsSaving,
  setSelectedBoardId,
  setShowSlackChannelForm,
  slackBinding,
}: OrganizationBoardsOptions) {
  const [boardName, setBoardName] = useState('');
  const [boardSlug, setBoardSlug] = useState('');
  const [boardSlugEdited, setBoardSlugEdited] = useState(false);
  const [boardMemberUserId, setBoardMemberUserId] = useState('');
  const [boardMemberRole, setBoardMemberRole] = useState<OrganizationBoardRole>('MEMBER');
  const [slackChannelId, setSlackChannelId] = useState('');
  const [slackChannelName, setSlackChannelName] = useState('');
  const [slackChannelRefresh, setSlackChannelRefresh] = useState<SlackChannelRefreshResponse | null>(null);
  const selectionRequest = useRef(0);

  useEffect(() => () => { selectionRequest.current++; }, [organization?.id]);

  const changeBoardName = (value: string) => {
    setBoardName(value);
    if (!boardSlugEdited) setBoardSlug(slugify(value));
  };

  const changeBoardSlug = (value: string) => {
    setBoardSlugEdited(true);
    setBoardSlug(slugify(value));
  };

  const selectBoard = async (boardId: string | null) => {
    if (!organization) return;
    const request = ++selectionRequest.current;
    setSelectedBoardId(boardId);
    setBoardMembers([]);
    setBoardSlackChannels([]);
    setConfirmBoardDelete(null);
    setConfirmBoardMemberRemove(null);
    setConfirmSlackChannelRemove(null);
    setShowSlackChannelForm(false);
    setSlackChannelRefresh(null);
    if (boardId === null) return;
    try {
      const [loadedBoardMembers, loadedBoardSlackChannels] = await Promise.all([
        listOrganizationBoardMembers(organization.id, boardId),
        listOrganizationBoardSlackChannels(organization.id, boardId),
      ]);
      if (request !== selectionRequest.current) return;
      setBoardMembers(loadedBoardMembers);
      setBoardSlackChannels(loadedBoardSlackChannels);
    } catch (boardError) {
      if (request !== selectionRequest.current) return;
      toast.error(boardError instanceof Error ? boardError.message : 'Could not load board members');
    }
  };

  const createBoard = async (event: FormEvent) => {
    event.preventDefault();
    if (!organization || !canCreateBoards) return;
    setIsSaving(true);
    try {
      const board = await createOrganizationBoard(organization.id, boardName.trim(), boardSlug.trim());
      setBoardName('');
      setBoardSlug('');
      setBoardSlugEdited(false);
      const loadedBoards = await listOrganizationBoards(organization.id);
      setBoards(loadedBoards);
      await selectBoard(board.id);
      toast.success('Project board created');
    } catch (boardError) {
      toast.error(boardError instanceof Error ? boardError.message : 'Could not create board');
    } finally {
      setIsSaving(false);
    }
  };

  const addBoardMember = async (event: FormEvent) => {
    event.preventDefault();
    if (!organization || !selectedBoard || !boardMemberUserId) return;
    setIsSaving(true);
    try {
      await addOrganizationBoardMember(organization.id, selectedBoard.id, boardMemberUserId, boardMemberRole);
      setBoardMemberUserId('');
      setBoardMemberRole('MEMBER');
      setBoardMembers(await listOrganizationBoardMembers(organization.id, selectedBoard.id));
      toast.success('Board member added');
    } catch (boardError) {
      toast.error(boardError instanceof Error ? boardError.message : 'Could not add board member');
    } finally {
      setIsSaving(false);
    }
  };

  const changeBoardRole = async (member: OrganizationBoardMember, role: OrganizationBoardRole) => {
    if (!organization || !selectedBoard) return;
    try {
      const updated = await changeOrganizationBoardMemberRole(organization.id, selectedBoard.id, member.user_id, role);
      setBoardMembers((items) => items.map((item) => item.user_id === updated.user_id ? updated : item));
      toast.success('Board role updated');
    } catch (boardError) {
      toast.error(boardError instanceof Error ? boardError.message : 'Could not update board role');
    }
  };

  const removeBoardMember = async (userId: string) => {
    if (!organization || !selectedBoard) return;
    try {
      await removeOrganizationBoardMember(organization.id, selectedBoard.id, userId);
      setBoardMembers((items) => items.filter((item) => item.user_id !== userId));
      setConfirmBoardMemberRemove(null);
      toast.success('Board member removed');
    } catch (boardError) {
      toast.error(boardError instanceof Error ? boardError.message : 'Could not remove board member');
    }
  };

  const addSlackChannelMapping = async (event: FormEvent) => {
    event.preventDefault();
    if (!organization || !selectedBoard || !slackBinding.slack_team_id) return;
    setIsSaving(true);
    try {
      await addOrganizationBoardSlackChannel(
        organization.id,
        selectedBoard.id,
        slackBinding.slack_team_id,
        slackChannelId.trim(),
        slackChannelName.trim() || undefined,
      );
      setSlackChannelId('');
      setSlackChannelName('');
      setShowSlackChannelForm(false);
      setBoardSlackChannels(await listOrganizationBoardSlackChannels(organization.id, selectedBoard.id));
      try {
        const refresh = await refreshOrganizationSlackChannels(organization.id);
        setSlackChannelRefresh(refresh);
        if (refresh.reconnect_required) {
          toast.error('Slack channel linked, but Slack needs updated permissions. Reconnect Slack once.');
        } else if (refresh.manual_invites_required.includes(slackChannelId.trim())) {
          toast.warning('Slack channel linked. Private channels need the app invited once inside Slack.');
        } else {
          toast.success(
            refresh.channels_joined > 0
              ? 'Slack channel linked and KanbanKaii joined the public channel'
              : 'Slack channel linked to project board',
          );
        }
      } catch {
        setSlackChannelRefresh(null);
        toast.warning('Slack channel linked, but KanbanKaii could not verify channel membership yet.');
      }
    } catch (channelError) {
      toast.error(channelError instanceof Error ? channelError.message : 'Could not link Slack channel');
    } finally {
      setIsSaving(false);
    }
  };

  const removeSlackChannelMapping = async (channel: OrganizationBoardSlackChannel) => {
    if (!organization || !selectedBoard) return;
    try {
      await removeOrganizationBoardSlackChannel(organization.id, selectedBoard.id, channel.slack_team_id, channel.slack_channel_id);
      setSlackChannelRefresh((current) => current ? {
        ...current,
        manual_invites_required: current.manual_invites_required.filter((channelId) => channelId !== channel.slack_channel_id),
      } : current);
      setBoardSlackChannels((items) =>
        items.filter((item) => item.slack_team_id !== channel.slack_team_id || item.slack_channel_id !== channel.slack_channel_id),
      );
      setConfirmSlackChannelRemove(null);
      toast.success('Slack channel unlinked');
    } catch (channelError) {
      toast.error(channelError instanceof Error ? channelError.message : 'Could not unlink Slack channel');
    }
  };

  const removeBoard = async (boardId: string) => {
    if (!organization) return;
    try {
      await deleteOrganizationBoard(organization.id, boardId);
      const loadedBoards = await listOrganizationBoards(organization.id);
      const nextBoardId = loadedBoards[0]?.id ?? null;
      setBoards(loadedBoards);
      await selectBoard(nextBoardId);
      setConfirmBoardDelete(null);
      toast.success('Project board deleted');
    } catch (boardError) {
      toast.error(boardError instanceof Error ? boardError.message : 'Could not delete board');
    }
  };

  return {
    addBoardMember,
    addSlackChannelMapping,
    boardMemberRole,
    boardMemberUserId,
    boardName,
    boardSlug,
    changeBoardName,
    changeBoardRole,
    changeBoardSlug,
    createBoard,
    removeBoard,
    removeBoardMember,
    removeSlackChannelMapping,
    selectBoard,
    setBoardMemberRole,
    setBoardMemberUserId,
    setSlackChannelId,
    setSlackChannelName,
    slackChannelRefresh,
    slackChannelId,
    slackChannelName,
  };
}
