const chatLog = document.querySelector("#chatLog");
const pinnedArea = document.querySelector("#pinnedArea");
const pinnedCollapsedIcon = document.querySelector("#pinnedCollapsedIcon");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const nameInput = document.querySelector("#nameInput");
const sendButton = document.querySelector("#sendButton");
const clearButton = document.querySelector("#clearButton");
const connectionStatus = document.querySelector("#connectionStatus");
const screenStatus = document.querySelector("#screenStatus");
const startShareButton = document.querySelector("#startShareButton");
const watchShareButton = document.querySelector("#watchShareButton");
const stopShareButton = document.querySelector("#stopShareButton");
const fitModeButton = document.querySelector("#fitModeButton");
const videoStage = document.querySelector("#videoStage");
const localVideo = document.querySelector("#localVideo");
const remoteVideo = document.querySelector("#remoteVideo");
const relayFrameImage = document.querySelector("#relayFrameImage");
const shareEmptyState = document.querySelector("#shareEmptyState");
const emojiButton = document.querySelector("#emojiButton");
const emojiTray = document.querySelector("#emojiTray");
const notifyButton = document.querySelector("#notifyButton");
const clientHost = document.querySelector("#clientHost");

let socket;
let reconnectTimer;
let history = [];
let pinnedMessageIds = [];
let pinnedCollapsed = localStorage.getItem("pinnedCollapsed") === "true";
let profile;
let screenState = { active: false };
let localStream;
let remoteStream;
let presenterPeers = new Map();
let viewerPeer;
let pendingViewerIce = [];
let pendingPresenterIce = new Map();
let fitMode = "contain";
let unreadCount = 0;
let notificationsEnabled = false;
let frameRelayTimer;
let frameCanvas;

const originalTitle = document.title;
const rtcConfig = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

function getAuthor() {
  return nameInput.value.trim() || profile.author;
}

function setStatus(text, connected) {
  connectionStatus.textContent = text;
  connectionStatus.dataset.connected = connected ? "true" : "false";
}

function setScreenStatus(text, active) {
  screenStatus.textContent = text;
  screenStatus.dataset.connected = active ? "true" : "false";
}

function setFitMode(nextMode) {
  fitMode = nextMode;
  videoStage.dataset.fitMode = fitMode;
  fitModeButton.textContent = fitMode === "contain" ? "비율 맞춤" : "화면 채움";
}

function notificationAvailable() {
  return "Notification" in window && window.isSecureContext;
}

function updateNotifyButton() {
  if (!notificationAvailable()) {
    notifyButton.textContent = "🔕";
    notifyButton.title = !window.isSecureContext
      ? "알림은 HTTPS 연결에서만 사용 가능합니다."
      : "이 브라우저는 알림을 지원하지 않습니다.";
    notifyButton.disabled = true;
    return;
  }

  notifyButton.dataset.enabled = notificationsEnabled ? "true" : "false";

  if (Notification.permission === "denied") {
    notifyButton.textContent = "🔕";
    notifyButton.title = "브라우저 설정에서 알림을 허용해야 합니다.";
  } else if (notificationsEnabled) {
    notifyButton.textContent = "🔔";
    notifyButton.title = "알림 켜짐 (클릭하여 끄기)";
  } else {
    notifyButton.textContent = "🔕";
    notifyButton.title = "알림 꺼짐 (클릭하여 켜기)";
  }
}

async function toggleNotifications() {
  if (!notificationAvailable()) {
    return;
  }

  if (Notification.permission === "default") {
    const result = await Notification.requestPermission();
    if (result === "granted") {
      notificationsEnabled = true;
    }
  } else if (Notification.permission === "granted") {
    notificationsEnabled = !notificationsEnabled;
  }

  updateNotifyButton();
}

function resetUnreadState() {
  unreadCount = 0;
  document.title = originalTitle;
}

function markUnread() {
  unreadCount += 1;
  document.title = `(${unreadCount}) ${originalTitle}`;
}

function notifyMessage(message) {
  if (!profile || message.client_id === profile.client_id || !document.hidden) {
    return;
  }

  markUnread();

  if (notificationAvailable() && Notification.permission === "granted" && notificationsEnabled) {
    const notification = new Notification(`${message.author}님의 새 메시지`, {
      body: message.text,
      tag: "ab-chat-message",
    });

    notification.onclick = () => {
      window.focus();
      notification.close();
      resetUnreadState();
    };
  }
}

function syncVideoRatio(video) {
  const width = video.videoWidth || 16;
  const height = video.videoHeight || 9;
  const ratio = `${width} / ${height}`;

  video.style.aspectRatio = ratio;
  videoStage.style.setProperty("--stream-ratio", ratio);
}

function bindVideoRatio(video) {
  video.addEventListener("loadedmetadata", () => syncVideoRatio(video));
  video.addEventListener("resize", () => syncVideoRatio(video));
}

bindVideoRatio(localVideo);
bindVideoRatio(remoteVideo);

function formatTime(isoString) {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(isoString));
}

function formatHost(host) {
  if (!host || host === "unknown") {
    return "IP 확인 안 됨";
  }

  if (host === "server-local") {
    return "A 노트북";
  }

  return host;
}

function findFirstUrl(text) {
  const match = text.match(/https?:\/\/[^\s]+/i);
  return match ? match[0] : null;
}

function isMapUrl(url) {
  try {
    const { hostname } = new URL(url);
    return (
      hostname.includes("map.naver.com") ||
      hostname.includes("naver.me") ||
      hostname.includes("place.map.kakao.com") ||
      hostname.includes("map.kakao.com") ||
      hostname.includes("kko.to")
    );
  } catch {
    return false;
  }
}

function buildMapCard(url) {
  const card = document.createElement("a");
  card.className = "map-card";
  card.href = url;
  card.target = "_blank";
  card.rel = "noreferrer";
  card.textContent = "지도 링크 열기";
  return card;
}

async function togglePin(messageId) {
  const isPinned = pinnedMessageIds.includes(messageId);
  const method = isPinned ? "DELETE" : "POST";

  try {
    const response = await fetch(`/api/pin/${messageId}`, { method });

    if (!response.ok) {
      throw new Error("고정 처리에 실패했습니다.");
    }
  } catch (error) {
    setStatus(error.message, false);
  }
}

function buildPinButton(messageId) {
  const isPinned = pinnedMessageIds.includes(messageId);
  const button = document.createElement("button");
  button.className = "pin-button";
  button.type = "button";
  button.textContent = isPinned ? "📌" : "📍";
  button.title = isPinned ? "고정 해제" : "메시지 고정";
  button.dataset.pinned = isPinned ? "true" : "false";
  button.addEventListener("click", () => togglePin(messageId));
  return button;
}

function togglePinnedCollapse() {
  pinnedCollapsed = !pinnedCollapsed;
  localStorage.setItem("pinnedCollapsed", pinnedCollapsed);
  updatePinnedVisibility();
}

function updatePinnedVisibility() {
  const hasPinned = pinnedMessageIds.length > 0;

  if (!hasPinned) {
    pinnedArea.hidden = true;
    pinnedCollapsedIcon.classList.remove("visible");
    return;
  }

  if (pinnedCollapsed) {
    pinnedArea.hidden = true;
    pinnedCollapsedIcon.classList.add("visible");
    pinnedCollapsedIcon.title = `고정된 메시지 ${pinnedMessageIds.length}개 펼치기`;
  } else {
    pinnedArea.hidden = false;
    pinnedCollapsedIcon.classList.remove("visible");
  }
}

function scrollToMessage(messageId) {
  const messageElements = chatLog.querySelectorAll(".message-row");
  let found = false;
  for (const element of messageElements) {
    if (element.dataset.messageId === messageId) {
      found = true;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
      element.style.animation = "highlight 1s ease";
      setTimeout(() => {
        element.style.animation = "";
      }, 1000);
      break;
    }
  }
  if (!found) {
    console.log("메시지를 찾을 수 없습니다:", messageId);
    console.log("사용 가능한 메시지 ID:", Array.from(messageElements).map(el => el.dataset.messageId));
  }
}

function renderPinnedMessages() {
  const pinned = history.filter((msg) => pinnedMessageIds.includes(msg.id));

  pinnedArea.replaceChildren();

  if (!pinned.length) {
    updatePinnedVisibility();
    return;
  }

  const header = document.createElement("div");
  header.className = "pinned-header";
  header.addEventListener("click", togglePinnedCollapse);

  const headerText = document.createElement("span");
  headerText.textContent = `고정된 메시지 (${pinned.length})`;

  const toggle = document.createElement("span");
  toggle.className = "pinned-toggle";
  toggle.textContent = "▼";

  header.append(headerText, toggle);
  pinnedArea.append(header);

  const messagesContainer = document.createElement("div");
  messagesContainer.className = "pinned-messages";

  for (const message of pinned) {
    const isMine = profile && message.client_id === profile.client_id;

    const row = document.createElement("div");
    row.className = `pinned-message-row ${isMine ? "mine" : "theirs"}`;

    const bubble = document.createElement("div");
    bubble.className = "pinned-message-bubble";
    bubble.style.cursor = "pointer";
    bubble.addEventListener("click", (e) => {
      if (e.target.className === "unpin-button") return;
      scrollToMessage(message.id);
    });

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${message.author} (${formatHost(message.host)}) · ${formatTime(message.created_at)}`;

    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = message.text;

    bubble.append(meta, text);

    const url = findFirstUrl(message.text);
    if (url && isMapUrl(url)) {
      bubble.append(buildMapCard(url));
    }

    const unpinButton = document.createElement("button");
    unpinButton.className = "unpin-button";
    unpinButton.type = "button";
    unpinButton.textContent = "×";
    unpinButton.title = "고정 해제";
    unpinButton.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePin(message.id);
    });

    bubble.append(unpinButton);
    row.append(bubble);
    messagesContainer.append(row);
  }

  pinnedArea.append(messagesContainer);
  updatePinnedVisibility();
}

function renderMessages(messages) {
  chatLog.replaceChildren();

  if (!messages.length) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state";
    emptyState.textContent = "화면을 공유하고 맛집 의견이나 지도 링크를 보내세요.";
    chatLog.append(emptyState);
    return;
  }

  for (const message of messages) {
    const isMine = profile && message.client_id === profile.client_id;

    const row = document.createElement("div");
    row.className = `message-row ${isMine ? "mine" : "theirs"}`;
    row.dataset.messageId = message.id;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${message.author} (${formatHost(message.host)}) · ${formatTime(message.created_at)}`;

    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = message.text;

    bubble.append(meta, text);

    const url = findFirstUrl(message.text);
    if (url && isMapUrl(url)) {
      bubble.append(buildMapCard(url));
    }

    const pinButton = buildPinButton(message.id);
    bubble.append(pinButton);

    row.append(bubble);
    chatLog.append(row);
  }

  chatLog.scrollTop = chatLog.scrollHeight;
  renderPinnedMessages();
}

function upsertMessage(message) {
  const exists = history.some((item) => item.id === message.id);

  if (!exists) {
    history.push(message);
  }

  renderMessages(history);
}

function sendSocket(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    throw new Error("서버에 연결되지 않았습니다.");
  }

  socket.send(JSON.stringify(payload));
}

function isPresenter() {
  return screenState.presenter_connection_id === profile?.connection_id;
}

function updateShareVisibility() {
  const presenter = isPresenter();
  const hasRemoteVideo = Boolean(remoteVideo.srcObject);
  const hasLocalVideo = Boolean(localVideo.srcObject);
  const hasRelayFrame = Boolean(relayFrameImage.src);

  localVideo.classList.toggle("visible", presenter && hasLocalVideo);
  remoteVideo.classList.toggle("visible", !presenter && hasRemoteVideo);
  relayFrameImage.classList.toggle("visible", !presenter && !hasRemoteVideo && hasRelayFrame);
  shareEmptyState.hidden = (presenter && hasLocalVideo) || (!presenter && (hasRemoteVideo || hasRelayFrame));

  startShareButton.disabled = !profile || Boolean(screenState.active);
  watchShareButton.disabled = !profile || !screenState.active || presenter;
  stopShareButton.disabled = !presenter || !screenState.active;
}

function handleScreenState(nextState) {
  const wasPresenter = isPresenter();
  screenState = nextState;

  if (!screenState.active) {
    setScreenStatus("화면 공유 대기", false);
    stopViewing();
    updateShareVisibility();
    return;
  }

  if (isPresenter()) {
    setScreenStatus("내 화면 공유 중", true);
  } else {
    if (wasPresenter) {
      stopScreenShare(false);
    }

    setScreenStatus(`${screenState.presenter_name || "상대방"} 화면 공유 중`, true);
    requestScreenWatch();
  }

  updateShareVisibility();
}

function safeSendSignal(toConnectionId, signal) {
  try {
    sendSocket({
      type: "webrtc-signal",
      to: toConnectionId,
      signal,
    });
  } catch {
    // The socket close handler will reconnect and restore the visible state.
  }
}

function createPeerConnection(peerConnectionId, role) {
  const pc = new RTCPeerConnection(rtcConfig);

  pc.addEventListener("icecandidate", (event) => {
    if (event.candidate) {
      safeSendSignal(peerConnectionId, {
        kind: "ice",
        candidate: event.candidate,
      });
    }
  });

  pc.addEventListener("connectionstatechange", () => {
    if (role === "viewer" && ["connected", "completed"].includes(pc.connectionState)) {
      setScreenStatus(`${screenState.presenter_name || "상대방"} 화면 보는 중`, true);
    }

    if (role === "viewer" && ["failed", "disconnected"].includes(pc.connectionState)) {
      setScreenStatus("화면 연결 재시도 필요", false);
    }
  });

  return pc;
}

async function startScreenShare() {
  if (!window.isSecureContext) {
    setScreenStatus("화면 공유는 HTTPS 또는 localhost 접속에서만 가능합니다.", false);
    return;
  }

  if (!navigator.mediaDevices?.getDisplayMedia) {
    setScreenStatus("이 브라우저는 화면 공유를 지원하지 않습니다.", false);
    return;
  }

  try {
    localStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    });
  } catch {
    setScreenStatus("화면 공유가 취소되었습니다.", false);
    return;
  }

  localVideo.srcObject = localStream;
  localVideo.play().catch(() => {});
  localStream.getVideoTracks()[0].addEventListener("ended", () => stopScreenShare(true));
  startFrameRelay();
  sendSocket({ type: "screen-start" });
  updateShareVisibility();
}

function startFrameRelay() {
  stopFrameRelay();

  frameCanvas = document.createElement("canvas");
  const context = frameCanvas.getContext("2d", { alpha: false });

  frameRelayTimer = window.setInterval(() => {
    if (!localStream || !localVideo.videoWidth || !localVideo.videoHeight) {
      return;
    }

    const maxWidth = 960;
    const scale = Math.min(1, maxWidth / localVideo.videoWidth);
    frameCanvas.width = Math.round(localVideo.videoWidth * scale);
    frameCanvas.height = Math.round(localVideo.videoHeight * scale);
    context.drawImage(localVideo, 0, 0, frameCanvas.width, frameCanvas.height);

    try {
      sendSocket({
        type: "screen-frame",
        frame: frameCanvas.toDataURL("image/jpeg", 0.58),
      });
    } catch {
      // WebRTC may still be working; socket recovery is handled elsewhere.
    }
  }, 700);
}

function stopFrameRelay() {
  if (frameRelayTimer) {
    window.clearInterval(frameRelayTimer);
  }

  frameRelayTimer = undefined;
  frameCanvas = undefined;
}

function closePresenterPeers() {
  for (const pc of presenterPeers.values()) {
    pc.close();
  }

  presenterPeers.clear();
  pendingPresenterIce.clear();
}

function stopScreenShare(notifyServer = true) {
  if (localStream) {
    for (const track of localStream.getTracks()) {
      track.stop();
    }
  }

  localStream = null;
  localVideo.srcObject = null;
  stopFrameRelay();
  closePresenterPeers();

  if (notifyServer && isPresenter() && socket?.readyState === WebSocket.OPEN) {
    sendSocket({ type: "screen-stop" });
  }

  updateShareVisibility();
}

function stopViewing() {
  if (viewerPeer) {
    viewerPeer.close();
    viewerPeer = null;
  }

  if (remoteStream) {
    for (const track of remoteStream.getTracks()) {
      track.stop();
    }
  }

  pendingViewerIce = [];
  remoteStream = null;
  remoteVideo.srcObject = null;
  relayFrameImage.removeAttribute("src");

  if (!isPresenter()) {
    closePresenterPeers();
    localVideo.srcObject = localStream;
  }
}

function requestScreenWatch() {
  if (!screenState.active || isPresenter()) {
    return;
  }

  stopViewing();
  setScreenStatus("공유 화면 연결 중", true);
  sendSocket({ type: "screen-watch" });
}

async function flushPresenterIce(connectionId) {
  const pc = presenterPeers.get(connectionId);
  const candidates = pendingPresenterIce.get(connectionId) || [];

  if (!pc || !pc.remoteDescription) {
    return;
  }

  for (const candidate of candidates) {
    await pc.addIceCandidate(candidate);
  }

  pendingPresenterIce.delete(connectionId);
}

async function flushViewerIce() {
  if (!viewerPeer?.remoteDescription) {
    return;
  }

  for (const candidate of pendingViewerIce) {
    await viewerPeer.addIceCandidate(candidate);
  }

  pendingViewerIce = [];
}

async function handleScreenWatch(viewer) {
  if (!localStream || !isPresenter()) {
    return;
  }

  const oldPeer = presenterPeers.get(viewer.connection_id);
  if (oldPeer) {
    oldPeer.close();
  }

  const pc = createPeerConnection(viewer.connection_id, "presenter");
  presenterPeers.set(viewer.connection_id, pc);

  for (const track of localStream.getTracks()) {
    pc.addTrack(track, localStream);
  }

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  safeSendSignal(viewer.connection_id, {
    kind: "offer",
    description: pc.localDescription,
  });
}

async function handleWebRtcSignal(fromConnectionId, signal) {
  if (!signal) {
    return;
  }

  if (signal.kind === "offer") {
    stopViewing();

    remoteStream = new MediaStream();
    remoteVideo.srcObject = remoteStream;

    viewerPeer = createPeerConnection(fromConnectionId, "viewer");
    viewerPeer.addEventListener("track", (event) => {
      remoteStream.addTrack(event.track);
      remoteVideo.play().catch(() => {});
      updateShareVisibility();
    });

    await viewerPeer.setRemoteDescription(signal.description);
    await flushViewerIce();

    const answer = await viewerPeer.createAnswer();
    await viewerPeer.setLocalDescription(answer);

    safeSendSignal(fromConnectionId, {
      kind: "answer",
      description: viewerPeer.localDescription,
    });
    return;
  }

  if (signal.kind === "answer") {
    const pc = presenterPeers.get(fromConnectionId);
    if (pc) {
      await pc.setRemoteDescription(signal.description);
      await flushPresenterIce(fromConnectionId);
    }
    return;
  }

  if (signal.kind === "ice") {
    const candidate = signal.candidate;
    const presenterPeer = presenterPeers.get(fromConnectionId);

    if (presenterPeer) {
      if (presenterPeer.remoteDescription) {
        await presenterPeer.addIceCandidate(candidate);
      } else {
        const candidates = pendingPresenterIce.get(fromConnectionId) || [];
        candidates.push(candidate);
        pendingPresenterIce.set(fromConnectionId, candidates);
      }
      return;
    }

    if (viewerPeer?.remoteDescription) {
      await viewerPeer.addIceCandidate(candidate);
    } else {
      pendingViewerIce.push(candidate);
    }
  }
}

function handleScreenFrame(frame) {
  if (isPresenter() || !screenState.active || typeof frame !== "string") {
    return;
  }

  relayFrameImage.src = frame;
  setScreenStatus(`${screenState.presenter_name || "상대방"} 화면 보는 중`, true);
  updateShareVisibility();
}

function connectSocket() {
  clearTimeout(reconnectTimer);
  setStatus("연결 중", false);

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/chat`);

  socket.addEventListener("open", () => {
    setStatus("연결됨", true);
    sendButton.disabled = false;
  });

  socket.addEventListener("message", async (event) => {
    const data = JSON.parse(event.data);

    try {
      if (data.type === "profile") {
        profile = data.profile;
        nameInput.value = profile.author;
        clientHost.textContent = `(${formatHost(profile.host)})`;
        renderMessages(history);
        updateShareVisibility();
        return;
      }

      if (data.type === "history") {
        history = data.messages;
        renderMessages(history);
        return;
      }

      if (data.type === "message") {
        upsertMessage(data.message);
        notifyMessage(data.message);
        return;
      }

      if (data.type === "pinned") {
        pinnedMessageIds = data.message_ids || [];
        renderPinnedMessages();
        renderMessages(history);
        return;
      }

      if (data.type === "screen-state") {
        handleScreenState(data.state);
        return;
      }

      if (data.type === "screen-watch") {
        await handleScreenWatch(data.viewer);
        return;
      }

      if (data.type === "webrtc-signal") {
        await handleWebRtcSignal(data.from, data.signal);
        return;
      }

      if (data.type === "screen-frame") {
        handleScreenFrame(data.frame);
        return;
      }

      if (data.type === "error") {
        setStatus(data.message, false);
      }
    } catch (error) {
      setScreenStatus(error.message || "화면 공유 연결 오류", false);
    }
  });

  socket.addEventListener("close", () => {
    setStatus("재연결 중", false);
    sendButton.disabled = true;
    reconnectTimer = setTimeout(connectSocket, 1200);
  });

  socket.addEventListener("error", () => {
    setStatus("연결 오류", false);
    socket.close();
  });
}

async function loadProfile() {
  const response = await fetch("/api/me");

  if (!response.ok) {
    throw new Error("사용자 정보를 불러오지 못했습니다.");
  }

  profile = await response.json();
  nameInput.value = profile.author;
  clientHost.textContent = `(${formatHost(profile.host)})`;
}

async function updateProfile() {
  const response = await fetch("/api/me", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ author: getAuthor() }),
  });

  if (!response.ok) {
    throw new Error("대화명을 저장하지 못했습니다.");
  }

  const updatedProfile = await response.json();
  profile.author = updatedProfile.author;
  nameInput.value = profile.author;
}

async function sendMessage(message) {
  await updateProfile();

  sendSocket({
    type: "chat",
    message,
    author: getAuthor(),
  });
}

function insertEmoji(emoji) {
  const start = messageInput.selectionStart ?? messageInput.value.length;
  const end = messageInput.selectionEnd ?? messageInput.value.length;
  const before = messageInput.value.slice(0, start);
  const after = messageInput.value.slice(end);

  messageInput.value = `${before}${emoji}${after}`;
  messageInput.focus();
  messageInput.setSelectionRange(start + emoji.length, start + emoji.length);
}

sendButton.disabled = true;
startShareButton.disabled = true;
watchShareButton.disabled = true;
setFitMode("contain");

nameInput.addEventListener("change", async () => {
  try {
    await updateProfile();
  } catch (error) {
    setStatus(error.message, false);
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  try {
    sendButton.disabled = true;
    await sendMessage(message);
    messageInput.value = "";
    messageInput.focus();
  } catch (error) {
    setStatus(error.message, false);
  } finally {
    sendButton.disabled = socket?.readyState !== WebSocket.OPEN;
  }
});

clearButton.addEventListener("click", async () => {
  await fetch("/api/history", { method: "DELETE" });
  messageInput.focus();
});

fitModeButton.addEventListener("click", () => {
  setFitMode(fitMode === "contain" ? "cover" : "contain");
});

emojiButton.addEventListener("click", () => {
  emojiTray.hidden = !emojiTray.hidden;
});

emojiTray.addEventListener("click", (event) => {
  if (event.target instanceof HTMLButtonElement) {
    insertEmoji(event.target.textContent);
    emojiTray.hidden = true;
  }
});

document.addEventListener("click", (event) => {
  if (!emojiTray.hidden && !emojiTray.contains(event.target) && event.target !== emojiButton) {
    emojiTray.hidden = true;
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    resetUnreadState();
  }
});

notifyButton.addEventListener("click", toggleNotifications);
pinnedCollapsedIcon.addEventListener("click", togglePinnedCollapse);
startShareButton.addEventListener("click", startScreenShare);
watchShareButton.addEventListener("click", requestScreenWatch);
stopShareButton.addEventListener("click", () => stopScreenShare(true));

async function initialize() {
  try {
    await loadProfile();
    updateNotifyButton();
    connectSocket();
  } catch (error) {
    setStatus(error.message, false);
  }
}

initialize();
