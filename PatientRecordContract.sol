// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title  PatientRecordContract
 * @author PRChain Solutions Ltd.
 * @notice Manages patient records on-chain for HealthCare Innovations Ltd.
 *
 * Design choices
 * ──────────────
 * • Records are stored in a mapping keyed by a uint256 ID so look-ups are O(1).
 * • Only the contract owner (deployer) may authorise healthcare providers.
 * • Only authorised providers may add or transfer records.
 * • Events are emitted for every state-changing action, enabling cheap
 *   off-chain indexing and audit trails.
 * • The `onlyAuthorised` modifier is applied before any sensitive function,
 *   keeping access-control logic in one place.
 */
contract PatientRecordContract {

    // ─────────────────────────────────────────
    //  State
    // ─────────────────────────────────────────

    /// @notice Total number of patient records ever added (never decremented).
    uint256 public totalRecords;

    /// @notice The account that deployed the contract — can authorise providers.
    address public owner;

    // ─────────────────────────────────────────
    //  Data structures
    // ─────────────────────────────────────────

    struct PatientRecord {
        uint256 id;
        string  patientName;
        uint256 dateOfBirth;      // Unix timestamp
        string  diagnosis;
        string  treatment;
        address currentProvider;  // authorised provider who currently holds the record
        uint256 createdAt;        // block.timestamp when record was added
        bool    exists;
    }

    /// @dev recordId => PatientRecord
    mapping(uint256 => PatientRecord) private records;

    /// @dev address => isAuthorised
    mapping(address => bool) public authorisedProviders;

    // ─────────────────────────────────────────
    //  Events
    // ─────────────────────────────────────────

    event ProviderAuthorised(address indexed provider, bool status);
    event RecordAdded(
        uint256 indexed recordId,
        string  patientName,
        address indexed addedBy
    );
    event RecordTransferred(
        uint256 indexed recordId,
        address indexed fromProvider,
        address indexed toProvider
    );

    // ─────────────────────────────────────────
    //  Modifiers
    // ─────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "PatientRecordContract: caller is not owner");
        _;
    }

    modifier onlyAuthorised() {
        require(
            authorisedProviders[msg.sender],
            "PatientRecordContract: caller is not an authorised provider"
        );
        _;
    }

    // ─────────────────────────────────────────
    //  Constructor
    // ─────────────────────────────────────────

    constructor() {
        owner = msg.sender;
        // The deploying account is automatically authorised as a provider
        authorisedProviders[msg.sender] = true;
        emit ProviderAuthorised(msg.sender, true);
    }

    // ─────────────────────────────────────────
    //  Owner functions
    // ─────────────────────────────────────────

    /**
     * @notice Grant or revoke provider authorisation.
     * @param  provider  The Ethereum address of the healthcare provider.
     * @param  status    true = authorise, false = revoke.
     */
    function setProviderAuthorisation(address provider, bool status)
        external
        onlyOwner
    {
        require(provider != address(0), "PatientRecordContract: zero address");
        authorisedProviders[provider] = status;
        emit ProviderAuthorised(provider, status);
    }

    // ─────────────────────────────────────────
    //  Provider functions
    // ─────────────────────────────────────────

    /**
     * @notice Add a new patient record.
     * @param  patientName  Full name of the patient.
     * @param  dateOfBirth  Patient's date of birth as a Unix timestamp.
     * @param  diagnosis    Primary diagnosis string.
     * @param  treatment    Prescribed treatment string.
     * @return recordId     The ID assigned to the new record.
     */
    function addRecord(
        string calldata patientName,
        uint256          dateOfBirth,
        string calldata  diagnosis,
        string calldata  treatment
    )
        external
        onlyAuthorised
        returns (uint256 recordId)
    {
        require(bytes(patientName).length > 0, "PatientRecordContract: empty name");

        recordId = ++totalRecords;   // IDs start at 1

        records[recordId] = PatientRecord({
            id:              recordId,
            patientName:     patientName,
            dateOfBirth:     dateOfBirth,
            diagnosis:       diagnosis,
            treatment:       treatment,
            currentProvider: msg.sender,
            createdAt:       block.timestamp,
            exists:          true
        });

        emit RecordAdded(recordId, patientName, msg.sender);
    }

    /**
     * @notice Transfer a patient record to another authorised provider.
     * @param  recordId    The ID of the record to transfer.
     * @param  toProvider  The address of the receiving provider.
     */
    function transferRecord(uint256 recordId, address toProvider)
        external
        onlyAuthorised
    {
        PatientRecord storage rec = records[recordId];

        require(rec.exists,                          "PatientRecordContract: record not found");
        require(rec.currentProvider == msg.sender,   "PatientRecordContract: caller does not hold this record");
        require(authorisedProviders[toProvider],      "PatientRecordContract: recipient not authorised");
        require(toProvider != msg.sender,             "PatientRecordContract: cannot transfer to self");

        address from = rec.currentProvider;
        rec.currentProvider = toProvider;

        emit RecordTransferred(recordId, from, toProvider);
    }

    // ─────────────────────────────────────────
    //  View functions
    // ─────────────────────────────────────────

    /**
     * @notice Retrieve a patient record by ID.
     *         Only authorised providers may call this function.
     */
    function getRecord(uint256 recordId)
        external
        view
        onlyAuthorised
        returns (PatientRecord memory)
    {
        require(records[recordId].exists, "PatientRecordContract: record not found");
        return records[recordId];
    }

    /**
     * @notice Check whether a given address is an authorised provider.
     */
    function isAuthorised(address provider) external view returns (bool) {
        return authorisedProviders[provider];
    }
}
