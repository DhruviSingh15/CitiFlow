// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CrossBorderSettlement
 * @notice CitiFlow prototype smart contract for immutable payment audit records.
 *
 * DISCLAIMER: This is a prototype for demonstration purposes.
 * It does not represent Citi's actual blockchain infrastructure.
 * The contract records an audit trail of CitiFlow orchestration decisions.
 */
contract CrossBorderSettlement {

    // ── Status lifecycle ─────────────────────────────────────
    enum Status {
        CREATED,            // 0
        RISK_APPROVED,      // 1
        ROUTE_SELECTED,     // 2
        SETTLEMENT_PENDING, // 3
        SETTLED,            // 4
        FAILED              // 5
    }

    // ── Settlement record ─────────────────────────────────────
    struct Settlement {
        uint256 id;
        string  transactionRef;   // e.g. "TXN1A2B3C"
        string  sender;
        string  recipient;
        uint256 amount;           // in smallest unit (paise)
        string  currency;
        string  selectedRail;     // e.g. "RAIL_B"
        Status  status;
        uint256 timestamp;        // block.timestamp at creation
        string  metadataHash;     // keccak256 of full payload (off-chain reference)
    }

    // ── State ─────────────────────────────────────────────────
    address public owner;
    uint256 public recordCount;

    mapping(uint256 => Settlement) public settlements;
    mapping(string  => uint256)    public refToId;    // txRef => record id

    // ── Events ────────────────────────────────────────────────
    event SettlementCreated(
        uint256 indexed id,
        string  indexed txRef,
        address indexed creator,
        uint256 amount,
        string  currency,
        string  rail
    );

    event StatusUpdated(
        uint256 indexed id,
        Status  oldStatus,
        Status  newStatus
    );

    // ── Modifiers ─────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "CrossBorderSettlement: not authorized");
        _;
    }

    modifier recordExists(uint256 id) {
        require(id > 0 && id <= recordCount, "CrossBorderSettlement: record not found");
        _;
    }

    // ── Constructor ───────────────────────────────────────────
    constructor() {
        owner = msg.sender;
    }

    // ── Write functions ───────────────────────────────────────

    /**
     * @notice Create a new settlement record.
     * @return id The on-chain record ID.
     */
    function createSettlement(
        string calldata txRef,
        string calldata sender,
        string calldata recipient,
        uint256         amount,
        string calldata currency,
        string calldata rail,
        string calldata metadataHash
    ) external onlyOwner returns (uint256 id) {
        require(bytes(txRef).length > 0,      "txRef required");
        require(refToId[txRef] == 0,          "txRef already exists");

        recordCount++;
        id = recordCount;

        settlements[id] = Settlement({
            id:             id,
            transactionRef: txRef,
            sender:         sender,
            recipient:      recipient,
            amount:         amount,
            currency:       currency,
            selectedRail:   rail,
            status:         Status.CREATED,
            timestamp:      block.timestamp,
            metadataHash:   metadataHash
        });

        refToId[txRef] = id;

        emit SettlementCreated(id, txRef, msg.sender, amount, currency, rail);
        return id;
    }

    /**
     * @notice Advance the status of a settlement record.
     */
    function updateStatus(uint256 id, Status newStatus)
        external
        onlyOwner
        recordExists(id)
    {
        Status old = settlements[id].status;
        settlements[id].status = newStatus;
        emit StatusUpdated(id, old, newStatus);
    }

    // ── Read functions ────────────────────────────────────────

    function getSettlement(uint256 id)
        external
        view
        recordExists(id)
        returns (Settlement memory)
    {
        return settlements[id];
    }

    function getByRef(string calldata txRef)
        external
        view
        returns (Settlement memory)
    {
        uint256 id = refToId[txRef];
        require(id > 0, "CrossBorderSettlement: ref not found");
        return settlements[id];
    }

    function getRecordCount() external view returns (uint256) {
        return recordCount;
    }
}
